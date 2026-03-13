"""System prompt construction for GutAgent."""

import json
import sqlite3
import os
from datetime import datetime, timedelta


def get_dynamic_context() -> str:
    """Pull recent data from all tables for the system prompt."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")

    if not os.path.exists(db_path):
        return "No data logged yet."

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    sections = []

    # Cutoffs in local time
    now = datetime.now()
    cutoff_7_days = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_30_days = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_3_days = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")

    # Current medications + recent changes
    meds = conn.execute("""
        SELECT me.*
        FROM medication_events me
        WHERE me.occurred_at >= ?
           OR (me.event_type = 'started' 
               AND me.id = (SELECT id FROM medication_events me2 
                            WHERE me2.medication = me.medication 
                            ORDER BY occurred_at DESC LIMIT 1))
        ORDER BY occurred_at DESC
    """, (cutoff_30_days,)).fetchall()
    if meds:
        lines = [
            f"- [id:{m['id']}] {m['occurred_at']} [{m['event_type']}]: {m['medication']}"
            f"{f' ({m['dose']})' if m['dose'] else ''}"
            f"{f' — {m['notes'][:100]}' if m['notes'] else ''}"
            for m in meds
        ]
        sections.append("## Medications (Current + Recent 30d)\n" + "\n".join(lines))

    # Latest labs
    labs = conn.execute("""
        SELECT *
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY test_name ORDER BY test_date DESC) as rn
            FROM labs
        )
        WHERE rn = 1
        ORDER BY test_date DESC, test_name
    """).fetchall()
    if labs:
        lines = [
            f"- {lab['test_name']}: "
            f"{f'{lab['value']} {lab['unit']}' if lab['value'] else '—'}"
            f"{f' (ref: {lab['reference_range']})' if lab['reference_range'] else ''}"
            f"{f' [{lab['status']}]' if lab['status'] else ''}"
            f"{f' — {lab['notes'][:100]}' if lab['notes'] else ''}"
            for lab in labs
        ]
        sections.append("## Labs (Latest)\n" + "\n".join(lines))

    # Recent vitals
    vitals = conn.execute("""
        SELECT * FROM vitals WHERE occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff_7_days,)).fetchall()
    if vitals:
        lines = []
        for v in vitals:
            notes_str = f" — {v['notes'][:100]}" if v['notes'] else ""
            if v['vital_type'] == 'blood_pressure':
                lines.append(f"- [id:{v['id']}] {v['occurred_at'][:10]}: {v['systolic']}/{v['diastolic']} HR:{v['heart_rate'] or '?'}{notes_str}")
            else:
                lines.append(f"- [id:{v['id']}] {v['occurred_at'][:10]}: {v['vital_type']} {v['value']} {v['unit']}{notes_str}")
        sections.append("## Vitals (7d)\n" + "\n".join(lines))

    # Recent meals
    meals = conn.execute("""
        SELECT m.*, mn.calories, mn.protein, mn.carbs, mn.fat, mn.fiber
        FROM meals m
        LEFT JOIN meal_nutrition mn ON m.id = mn.meal_id
        WHERE m.occurred_at >= ?
        ORDER BY m.occurred_at DESC
    """, (cutoff_3_days,)).fetchall()
    if meals:
        lines = [
            f"- [id:{m['id']}] {m['occurred_at']}: {m['meal_type'] or 'meal'} — {m['description']}"
            f"{f' [{int(m['calories'])}cal {int(m['protein'])}g]' if m['calories'] else ''}"
            for m in meals
        ]
        sections.append("## Meals (3d)\n" + "\n".join(lines))

    # Recent symptoms
    symptoms = conn.execute("""
        SELECT * FROM symptoms WHERE occurred_at >= ?
        ORDER BY occurred_at DESC
    """, (cutoff_7_days,)).fetchall()
    if symptoms:
        lines = [
            f"- [id:{s['id']}] {s['occurred_at']}: {s['symptom']} ({s['severity']})"
            f"{f' — {s['notes'][:100]}' if s['notes'] else ''}"
            for s in symptoms
        ]
        sections.append("## Symptoms (7d)\n" + "\n".join(lines))

    # Recent sleep
    sleep = conn.execute("""
        SELECT * FROM sleep WHERE occurred_at >= ? ORDER BY occurred_at DESC
    """, (cutoff_3_days,)).fetchall()
    if sleep:
        lines = [
            f"- [id:{s['id']}] {s['occurred_at'][:10]}: {s['hours'] or '?'}h {s['quality'] or ''}"
            f"{f' — {s['notes'][:100]}' if s['notes'] else ''}"
            for s in sleep
        ]
        sections.append("## Sleep (3d)\n" + "\n".join(lines))

    # Recent exercise
    exercise = conn.execute("""
        SELECT * FROM exercise WHERE occurred_at >= ? ORDER BY occurred_at DESC
    """, (cutoff_3_days,)).fetchall()
    if exercise:
        lines = [
            f"- [id:{e['id']}] {e['occurred_at'][:10]}: {e['activity']} {e['duration_minutes'] or '?'}min"
            f"{f' — {e['notes'][:100]}' if e['notes'] else ''}"
            for e in exercise
        ]
        sections.append("## Exercise (3d)\n" + "\n".join(lines))

    # Recent journal
    journal = conn.execute("""
        SELECT * FROM journal WHERE logged_at >= ? ORDER BY logged_at DESC LIMIT 5
    """, (cutoff_3_days,)).fetchall()
    if journal:
        lines = [f"- [id:{j['id']}] {j['logged_at'][:10]}: {j['description'][:100]}" for j in journal]
        sections.append("## Journal (3d)\n" + "\n".join(lines))

    # Saved recipes
    recipes = conn.execute("SELECT name FROM recipes ORDER BY name").fetchall()
    if recipes:
        sections.append("## Recipes: " + ", ".join(r['name'] for r in recipes))

    conn.close()
    return "\n\n".join(sections) if sections else "No data logged yet."


def get_nutrition_alerts_text() -> str:
    """Get formatted nutrition alerts for the system prompt."""
    from gutagent.db.models import get_nutrition_alerts

    try:
        alerts = get_nutrition_alerts(days=3)
    except Exception:
        return ""

    if not alerts:
        return ""

    lines = ["## Nutrition Alerts (Last 3 Days)"]
    for alert in alerts:
        nutrient_name = alert["nutrient"].replace("_", " ").title()

        if alert["type"] == "deficiency":
            severity_marker = "⚠️" if alert["severity"] == "low" else "🔴"
            lines.append(
                f"{severity_marker} Low {nutrient_name}: {alert['daily_average']}{alert['unit']}/day "
                f"({alert['percent_of_rda']}% of {alert['target']}{alert['unit']} target)"
            )
        else:
            severity_marker = "⚠️" if alert["severity"] == "high" else "🔴"
            lines.append(
                f"{severity_marker} High {nutrient_name}: {alert['daily_average']}{alert['unit']}/day "
                f"(exceeds {alert['upper_limit']}{alert['unit']} safe limit)"
            )

    return "\n".join(lines)


def build_static_system_prompt(profile: dict) -> str:
    """
    Build the STATIC portion of the system prompt.
    This part is cached and should not change between calls.
    """
    profile_text = json.dumps(profile, indent=2)

    return f"""You are GutAgent, a personalized dietary assistant for a patient with 
inflammatory bowel disease. You are warm, practical, and evidence-informed — like a 
knowledgeable friend who happens to understand IBD nutrition deeply.

## Patient's Medical Profile
{profile_text}

## Core Behavior

PROACTIVE LOGGING:
- When the user mentions eating ANYTHING, call log_meal immediately — even casual mentions
- Parse meals into individual food items with estimated nutrition (calories, protein, carbs, fat, fiber, AND micronutrients)
- Use your knowledge to estimate nutrition for any food, including Indian cuisine
- Check for saved recipes first; if a dish matches a saved recipe, use recipe_name parameter
- When the user mentions ANY physical or mental symptom, call log_symptom immediately
- When the user mentions ANY medication change, call log_medication_event immediately
- When the user mentions ANY vital reading, call log_vital immediately
- When the user mentions sleep (hours or quality), call log_sleep
- When the user mentions exercise or physical activity, call log_exercise
- You don't need to ask permission to log. Just do it and confirm briefly.
- Journal entries are only logged when the user explicitly wants to note something

NUTRITION TRACKING:
- Estimate nutrition directly using your knowledge — no external lookup needed
- Track both macros (calories, protein, carbs, fat, fiber) AND micronutrients (B12, D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, vitamin A, vitamin C)
- Provide reasonable estimates even for regional/ethnic foods
- Include brief nutrition summary when logging meals (e.g., "~450 cal, 32g protein")
- When discussing nutrition, proactively mention any alerts if relevant
- Offer to save recipes when the user describes dishes they eat often

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
- If the patient reports a symptom, check recent meals using query_logs
- Note correlations between medication changes and symptoms/vitals
- Flag potential new triggers or confirm known ones
- Consider nutrition gaps when interpreting symptoms (fatigue + low B12, etc.)

ANALYZING TRENDS — ALWAYS CHECK BASELINE:
- When analyzing ANY trend (BP, symptoms, weight, sleep, etc.), don't just show recent data — establish what "normal" looks like for this patient
- Use query_logs to pull historical data to find the baseline pattern

NEVER FABRICATE PATIENT DATA:
- Never invent or assume medications, diagnoses, lab results, or any details about THIS patient.
- Only state what is explicitly in the patient's profile or database records.
- If unsure whether the patient is on a medication or has a condition, ask — don't assume.
- You CAN and SHOULD use your general medical knowledge to explain conditions, suggest questions for doctors, interpret patterns, and provide dietary guidance.

CORRECTIONS:
- Entry IDs are shown in square brackets like [id:47] in the recent data below.
- If the user asks to correct or delete an entry, use correct_log with the correct entry_id.
- Never guess IDs — only use IDs you can see in the recent data.
- For entries older than the recent data window, use query_logs with query_type="date_search", the specific date (YYYY-MM-DD), and table (meals, symptoms, vitals, etc.) to find the entry and its ID.
- Example: "correct my lunch from March 5th" → first call query_logs with query_type="date_search", date="2026-03-05", table="meals" to get the entry ID, then use correct_log.
- Never create a new entry when a correction is needed.

SAVING SUGGESTIONS:
- When you suggest medical tests, deficiency checks, or important items to discuss with a doctor, offer to save them if the user seems interested.
- If the user says "save that", "remember that", or "add that to my list", use update_profile to save to suggestions.tests_to_request.
- Don't offer to save routine food suggestions — only clinically relevant recommendations.

RECIPES:
- When the user describes a dish they make often, offer to save it as a recipe
- Saved recipes enable accurate nutrition and spice tracking for repeated meals
- When logging a meal that matches a saved recipe name, use the recipe_name parameter
- Check for saved recipes when logging meals that match recipe names
"""


def build_dynamic_context() -> str:
    """
    Build the DYNAMIC portion of the system prompt.
    This changes between calls and is NOT cached.
    """
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    dynamic_context = get_dynamic_context()
    nutrition_alerts = get_nutrition_alerts_text()

    return f"""## Current Date and Time
{today}

## Current Data from Patient's Records
{dynamic_context}

{nutrition_alerts}"""


def build_system_prompt(profile: dict) -> str:
    """
    Build the complete system prompt (for backward compatibility).
    Prefer using build_static_system_prompt() + build_dynamic_context() separately
    for prompt caching.
    """
    return build_static_system_prompt(profile) + "\n\n" + build_dynamic_context()
