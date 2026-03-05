"""
Generate a doctor-ready health report from GutAgent data.

Usage:
    python utils/generate_report.py
    python utils/generate_report.py --days 30
    python utils/generate_report.py --output my_report.pdf

Pulls from profile.json and gutagent.db to create a clean PDF summary.
"""

import sqlite3
import json
import os
import sys
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib import colors

# Paths
BASE_DIR = os.path.join(os.path.dirname(__file__), "../..")
DB_PATH = os.path.join(BASE_DIR, "data", "gutagent.db")
PROFILE_PATH = os.path.join(BASE_DIR, "data", "profile.json")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_profile():
    with open(PROFILE_PATH, "r") as f:
        return json.load(f)


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='ReportTitle',
        parent=styles['Title'],
        fontSize=18,
        textColor=HexColor('#1a5276'),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='SectionHead',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=HexColor('#1a5276'),
        spaceBefore=16,
        spaceAfter=8,
        borderWidth=0,
        borderPadding=0,
        borderColor=HexColor('#1a5276'),
    ))
    styles.add(ParagraphStyle(
        name='SubHead',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=HexColor('#2c3e50'),
        spaceBefore=10,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='BodyText2',
        parent=styles['Normal'],
        fontSize=9,
        leading=13,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='SmallNote',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#777777'),
        spaceAfter=2,
    ))
    return styles


def build_table(data, col_widths=None):
    """Build a formatted table from list of lists."""
    if not data:
        return None
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#d4e6f1')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#1a5276')),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f8f9fa')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(style)
    return t


def generate_report(days_back=30, output_path=None):
    if output_path is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        reports_dir = os.path.join(BASE_DIR, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        output_path = os.path.join(reports_dir, f"health_report_{date_str}.pdf")

    profile = load_profile()
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    styles = build_styles()
    story = []

    # Title
    story.append(Paragraph("Patient Health Report", styles['ReportTitle']))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y')} | "
        f"Reporting period: last {days_back} days",
        styles['SmallNote']
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=HexColor('#1a5276')))
    story.append(Spacer(1, 8))

    # Patient summary
    personal = profile.get("personal", {})
    conditions = profile.get("conditions", {})
    story.append(Paragraph("Patient Summary", styles['SectionHead']))
    summary_lines = []
    if personal.get("dob"):
        age = (datetime.now() - datetime.strptime(personal["dob"], "%Y-%m-%d")).days // 365
        summary_lines.append(f"Age: {age} | Sex: {personal.get('sex', '')} | Status: {personal.get('menopause_status', '')}")
    summary_lines.append(f"Primary condition: {conditions.get('primary', 'N/A')}")
    for line in summary_lines:
        story.append(Paragraph(line, styles['BodyText2']))

    # Current medications
    story.append(Paragraph("Current Medications", styles['SectionHead']))
    meds = conn.execute("""
        SELECT medication, event_type, occurred_at, dose, notes
        FROM medication_events
        ORDER BY occurred_at
    """).fetchall()

    active = {}
    for m in meds:
        if m['event_type'] == 'snapshot':
            continue
        name = m['medication'].lower()
        if m['event_type'] == 'started':
            active[name] = m
        elif m['event_type'] == 'stopped':
            active.pop(name, None)
        elif m['event_type'] in ('dose_changed', 'side_effect'):
            active[name] = m

    if active:
        med_data = [['Medication', 'Dose', 'Since', 'Notes']]
        for name, m in active.items():
            med_data.append([
                m['medication'],
                m['dose'] or '—',
                m['occurred_at'][:10] if m['occurred_at'] else '—',
                m['notes'] or '—'
            ])
        story.append(build_table(med_data, col_widths=[1.8*inch, 1.2*inch, 1*inch, 2.5*inch]))
    else:
        story.append(Paragraph("No active medications recorded.", styles['BodyText2']))

    # Recent medication changes
    recent_changes = conn.execute("""
        SELECT medication, event_type, occurred_at, dose, notes
        FROM medication_events
        WHERE event_type != 'snapshot' AND occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff,)).fetchall()

    if recent_changes:
        story.append(Paragraph("Recent Medication Changes", styles['SubHead']))
        for m in recent_changes:
            dose_str = f" ({m['dose']})" if m['dose'] else ""
            notes_str = f" — {m['notes']}" if m['notes'] else ""
            story.append(Paragraph(
                f"{m['occurred_at'][:10]}: {m['medication']}{dose_str} — {m['event_type']}{notes_str}",
                styles['BodyText2']
            ))

    # Blood pressure trends
    story.append(Paragraph("Blood Pressure Readings", styles['SectionHead']))
    bp_rows = conn.execute("""
        SELECT systolic, diastolic, heart_rate, occurred_at, notes
        FROM vitals
        WHERE vital_type = 'blood_pressure'
        ORDER BY occurred_at
    """).fetchall()

    if bp_rows:
        bp_data = [['Date', 'Systolic', 'Diastolic', 'HR', 'Notes']]
        for r in bp_rows:
            bp_data.append([
                r['occurred_at'][:16] if r['occurred_at'] else '—',
                str(r['systolic']) if r['systolic'] else '—',
                str(r['diastolic']) if r['diastolic'] else '—',
                str(r['heart_rate']) if r['heart_rate'] else '—',
                (r['notes'] or '—')[:60]
            ])
        story.append(build_table(bp_data, col_widths=[1.5*inch, 0.8*inch, 0.8*inch, 0.6*inch, 2.8*inch]))

        # Summary stats
        systolics = [r['systolic'] for r in bp_rows if r['systolic']]
        diastolics = [r['diastolic'] for r in bp_rows if r['diastolic']]
        if systolics:
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"Systolic range: {min(systolics)}-{max(systolics)} (avg {sum(systolics)//len(systolics)}) | "
                f"Diastolic range: {min(diastolics)}-{max(diastolics)} (avg {sum(diastolics)//len(diastolics)}) | "
                f"Total readings: {len(systolics)}",
                styles['SmallNote']
            ))

    # Weight trend
    story.append(Paragraph("Weight History", styles['SectionHead']))
    weight_rows = conn.execute("""
        SELECT value, unit, occurred_at
        FROM vitals WHERE vital_type = 'weight'
        ORDER BY occurred_at
    """).fetchall()

    if weight_rows:
        wt_data = [['Date', 'Weight']]
        for r in weight_rows:
            wt_data.append([
                r['occurred_at'][:10] if r['occurred_at'] else '—',
                f"{r['value']} {r['unit']}" if r['value'] else '—'
            ])
        story.append(build_table(wt_data, col_widths=[2*inch, 2*inch]))

    # Lab results
    story.append(PageBreak())
    story.append(Paragraph("Lab Results", styles['SectionHead']))
    labs = conn.execute("""
        SELECT test_date, test_name, value, unit, reference_range, status, notes
        FROM labs
        ORDER BY test_date DESC, status, test_name
    """).fetchall()

    if labs:
        # Group by test date
        current_date = None
        lab_data = None
        for lab in labs:
            if lab['test_date'] != current_date:
                if lab_data and len(lab_data) > 1:
                    story.append(build_table(lab_data, col_widths=[2*inch, 1*inch, 1*inch, 1*inch, 1.5*inch]))
                    story.append(Spacer(1, 8))
                current_date = lab['test_date']
                story.append(Paragraph(f"Test Date: {current_date}", styles['SubHead']))
                lab_data = [['Test', 'Result', 'Reference', 'Status', 'Notes']]

            val = f"{lab['value']} {lab['unit']}" if lab['value'] else '—'
            status = lab['status'] or ''
            flag = ' **' if status in ('high', 'low', 'critical', 'abnormal') else ''
            lab_data.append([
                lab['test_name'],
                val,
                lab['reference_range'] or '—',
                status + flag,
                (lab['notes'] or '—')[:60]
            ])

        if lab_data and len(lab_data) > 1:
            story.append(build_table(lab_data, col_widths=[2*inch, 1*inch, 1*inch, 1*inch, 1.5*inch]))

    # Meal log
    story.append(PageBreak())
    story.append(Paragraph(f"Meal Log (Last {days_back} Days)", styles['SectionHead']))
    meals = conn.execute("""
        SELECT occurred_at, meal_type, description, foods
        FROM meals WHERE occurred_at >= ?
        ORDER BY occurred_at
    """, (cutoff,)).fetchall()

    if meals:
        meal_data = [['Date', 'Type', 'Description', 'Foods']]
        for m in meals:
            foods = json.loads(m['foods']) if m['foods'] else []
            meal_data.append([
                m['occurred_at'][:16] if m['occurred_at'] else '—',
                m['meal_type'] or '—',
                (m['description'] or '—')[:50], ', '.join(foods)[:50]
            ])
        story.append(build_table(meal_data, col_widths=[1.3*inch, 0.8*inch, 2.2*inch, 2.2*inch]))
    else:
        story.append(Paragraph("No meals logged in this period.", styles['BodyText2']))

    # Symptom log
    story.append(Paragraph(f"Symptom Log (Last {days_back} Days)", styles['SectionHead']))
    symptoms = conn.execute("""
        SELECT occurred_at, symptom, severity, notes
        FROM symptoms WHERE occurred_at >= ?
        ORDER BY occurred_at
    """, (cutoff,)).fetchall()

    if symptoms:
        sx_data = [['Date', 'Symptom', 'Severity', 'Notes']]
        for s in symptoms:
            sx_data.append([
                s['occurred_at'][:16] if s['occurred_at'] else '—',
                s['symptom'] or '—',
                str(s['severity']) if s['severity'] else '—',
                (s['notes'] or '—')[:60]
            ])
        story.append(build_table(sx_data, col_widths=[1.3*inch, 1.2*inch, 0.7*inch, 3.3*inch]))
    else:
        story.append(Paragraph("No symptoms logged in this period.", styles['BodyText2']))

    # Dietary triggers summary
    story.append(Paragraph("Known Dietary Triggers", styles['SectionHead']))
    dietary = profile.get("dietary", {})
    triggers = dietary.get("known_triggers", {})
    if triggers:
        for category, items in triggers.items():
            if isinstance(items, list):
                story.append(Paragraph(
                    f"<b>{category.title()}:</b> {', '.join(items)}",
                    styles['BodyText2']
                ))
            else:
                story.append(Paragraph(
                    f"<b>{category.title()}:</b> {items}",
                    styles['BodyText2']
                ))

    safe = dietary.get("safe_foods", [])
    if safe:
        story.append(Paragraph(f"<b>Safe foods:</b> {', '.join(safe)}", styles['BodyText2']))

    # Key conditions for reference
    story.append(Paragraph("Active Conditions", styles['SectionHead']))
    if conditions.get("other"):
        for cond in conditions["other"]:
            story.append(Paragraph(f"- {cond}", styles['BodyText2']))

    ruled_out = conditions.get("ruled_out", [])
    if ruled_out:
        story.append(Paragraph(f"<b>Ruled out:</b> {', '.join(ruled_out)}", styles['BodyText2']))

    # Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor('#cccccc')))
    story.append(Paragraph(
        "Generated by GutAgent. This report is a patient-maintained log and should be reviewed "
        "in clinical context. Data accuracy depends on patient self-reporting.",
        styles['SmallNote']
    ))

    conn.close()

    # Build PDF
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.6*inch,
        bottomMargin=0.6*inch,
        leftMargin=0.7*inch,
        rightMargin=0.7*inch,
    )
    doc.build(story)
    print(f"Report generated: {output_path}")
    return output_path


if __name__ == "__main__":
    days = 30
    output = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--days" and i + 1 < len(args):
            days = int(args[i + 1])
            i += 2
        elif args[i] == "--output" and i + 1 < len(args):
            output = args[i + 1]
            i += 2
        else:
            i += 1
    generate_report(days_back=days, output_path=output)