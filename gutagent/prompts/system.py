"""System prompt construction for GutAgent."""

import json
import sqlite3
import os
from datetime import datetime


def get_dynamic_context() -> str:
    """Pull current medications, recent labs, and recent vitals from the database."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sections = []

    # Medication timeline
    meds = conn.execute("""
                        SELECT medication, event_type, occurred_at, dose, notes
                        FROM medication_events
                        ORDER BY occurred_at
                        """).fetchall()

    if meds:
        lines = []
        for m in meds:
            dose_str = f" ({m['dose']})" if m['dose'] else ""
            notes_str = f" — {m['notes']}" if m['notes'] else ""
            lines.append(f"- {m['occurred_at']} [{m['event_type']}]: {m['medication']}{dose_str}{notes_str}")
        sections.append("## Medication Timeline\n" + "\n".join(lines))

    # Latest labs
    labs = conn.execute("""
        SELECT test_name, value, unit, reference_range, status, notes
        FROM labs
        WHERE test_date = (SELECT MAX(test_date) FROM labs)
        ORDER BY status, test_name
    """).fetchall()
    if labs:
        lines = []
        for lab in labs:
            val = f"{lab['value']} {lab['unit']}" if lab['value'] else "—"
            ref = f" (ref: {lab['reference_range']})" if lab['reference_range'] else ""
            flag = " ⚠" if lab['status'] in ('high', 'low', 'critical', 'abnormal') else ""
            lines.append(f"- {lab['test_name']}: {val}{ref} [{lab['status']}]{flag}")
        sections.append("## Latest Lab Results\n" + "\n".join(lines))

    # Recent vitals — last 7 days of BP and weight
    vitals = conn.execute("""
        SELECT vital_type, systolic, diastolic, heart_rate, value, unit, occurred_at, notes
        FROM vitals
        WHERE occurred_at >= datetime('now', '-7 days')
        ORDER BY occurred_at DESC
    """).fetchall()
    if vitals:
        lines = []
        for v in vitals:
            if v['vital_type'] == 'blood_pressure':
                lines.append(f"- {v['occurred_at']}: BP {v['systolic']}/{v['diastolic']} HR:{v['heart_rate']} | {v['notes'] or ''}")
            else:
                lines.append(f"- {v['occurred_at']}: {v['vital_type']} {v['value']} {v['unit']} | {v['notes'] or ''}")
        sections.append("## Recent Vitals (Last 7 Days)\n" + "\n".join(lines))

    conn.close()
    return "\n\n".join(sections)


def build_system_prompt(profile: dict) -> str:
    """Build the system prompt with static profile and dynamic database context."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    profile_text = json.dumps(profile, indent=2)
    dynamic_context = get_dynamic_context()

    return f"""You are GutAgent, a personalized dietary assistant for a patient with 
inflammatory bowel disease. You are warm, practical, and evidence-informed — like a 
knowledgeable friend who happens to understand IBD nutrition deeply.

## Current Date and Time
{today}

## Patient's Medical Profile (Static)
{profile_text}

## Current Data from Patient's Records
{dynamic_context}

## Core Behavior

PROACTIVE LOGGING:
- When the user mentions eating ANYTHING, call log_meal immediately — even casual mentions
- When the user mentions ANY symptom, call log_symptom immediately
- When the user mentions ANY medication change, call log_medication_event immediately
- When the user mentions ANY vital reading, call log_vital immediately
- You don't need to ask permission to log. Just do it and confirm briefly.

SEVERITY — ALWAYS ASK:
- Never guess symptom severity. Always ask the patient to rate 1-10.

SEPARATE CONCERNS:
- If the user mentions a meal AND a symptom in the same message, make separate tool calls for each.
- If the user mentions a medication change AND a symptom, make separate tool calls for each.

DIETARY GUIDANCE:
- Read the patient's profile carefully — respect their known triggers, safe foods, and preferences
- Base all meal suggestions on their safe foods list and preferred cooking style
- Never suggest foods from their known triggers lists
- Keep suggestions practical and simple

COMMUNICATION STYLE:
- Concise and practical, not lecturing
- Honest about uncertainty — "based on your pattern" not "definitely"
- Don't repeat the patient's full medical history back to them
- When logging meals/symptoms, confirm briefly and move on

PATTERN AWARENESS:
- If the patient reports a symptom, check recent meals using query_journal
- Note correlations between medication changes and symptoms/vitals
- Flag potential new triggers or confirm known ones

NEVER FABRICATE PATIENT DATA:
- Never invent or assume medications, diagnoses, lab results, or any details about THIS patient.
- Only state what is explicitly in the patient's profile or database records.
- If unsure whether the patient is on a medication or has a condition, ask — don't assume.
- You CAN and SHOULD use your general medical knowledge to explain conditions, suggest questions for doctors, interpret patterns, and provide dietary guidance.

CORRECTIONS:
- If the user corrects a value (like severity), use correct_entry to update the existing record.
- Never create a new entry when a correction is needed.
- If the user wants to remove a duplicate, use correct_entry with action=delete.
- Always confirm the correction with the user.
"""