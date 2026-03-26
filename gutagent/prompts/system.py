"""System prompt construction for GutAgent."""

import json
from datetime import datetime, timedelta

from gutagent.db import (
    get_recent_meals,
    get_recent_symptoms,
    get_recent_vitals,
    get_current_and_recent_meds,
    get_latest_labs_per_test,
    get_recent_sleep,
    get_recent_exercise,
    get_recent_journal,
    list_recipes,
    get_nutrition_summary,
    get_nutrition_alerts,
)
from gutagent.logging_config import get_logger

logger = get_logger("prompts")


def get_patient_data() -> str:
    """Pull recent data from all tables — changes when user logs something.

    This is the 'semi-static' context that can be cached separately from
    the truly dynamic turn context (recent_logs, last_exchange).
    """
    sections = []

    # Medications - current + recent 30 days
    try:
        meds = get_current_and_recent_meds(days_back=30)
        if meds:
            lines = [
                f"- [id:{m['id']}] {m['occurred_at']} [{m['event_type']}]: {m['medication']}"
                f"{f' ({m.get('dose')})' if m.get('dose') else ''}"
                f"{f' — {m.get('notes', '')[:70]}' if m.get('notes') else ''}"
                for m in meds
            ]
            sections.append("## Medications (Current + Recent)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Medications section: %s", e)

    # Labs - latest value for each test type
    try:
        labs = get_latest_labs_per_test()
        if labs:
            lines = [
                f"- {lab['test_name']} ({lab['test_date']}): "
                f"{f'{lab.get('value')} {lab.get('unit', '')}' if lab.get('value') else '—'}"
                f"{f' (ref: {lab.get('reference_range')})' if lab.get('reference_range') else ''}"
                f"{f' [{lab['status']}]' if lab.get('status') else ''}"
                f"{f' — {lab.get('notes', '')[:70]}' if lab.get('notes') else ''}"
                for lab in labs
            ]
            sections.append("## Labs (Latest)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Labs section: %s", e)

    # Vitals - last 3d
    try:
        vitals = get_recent_vitals(days_back=3)
        if vitals:
            lines = []
            for v in vitals:
                if v['vital_type'] == 'blood_pressure':
                    reading = f"{v['systolic']}/{v['diastolic']} HR:{v.get('heart_rate') or '?'}"
                else:
                    reading = f"{v.get('value', '?')} {v.get('unit', '')}"
                note = f" — {v.get('notes', '')[:70]}" if v.get('notes') else ""
                lines.append(f"- [id:{v['id']}] {v['occurred_at'][:10]} {v['vital_type']}: {reading}{note}")
            sections.append("## Vitals (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Vitals section: %s", e)

    # Meals - last 3d (descriptions only, nutrition in summary)
    try:
        meals = get_recent_meals(days_back=3)
        if meals:
            lines = [
                f"- [id:{m['id']}] {m['occurred_at'][:10]} {m.get('meal_type') or 'meal'}: {m['description']}"
                for m in meals
            ]
            sections.append("## Meals (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Meals section: %s", e)

    # Symptoms - last 3d
    try:
        symptoms = get_recent_symptoms(days_back=3)
        if symptoms:
            lines = [
                f"- [id:{s['id']}] {s['occurred_at']}: {s['symptom']} ({s['severity']})"
                f"{f' — {s.get('notes', '')[:70]}' if s.get('notes') else ''}"
                for s in symptoms
            ]
            sections.append("## Symptoms (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Symptoms section: %s", e)

    # Sleep - last 3d
    try:
        sleep = get_recent_sleep(days_back=3)
        if sleep:
            lines = [
                f"- [id:{s['id']}] {str(s['occurred_at'])[:10]}: {s.get('hours') or '?'}h {s.get('quality') or ''}"
                f"{f' — {s.get('notes', '')[:70]}' if s.get('notes') else ''}"
                for s in sleep
            ]
            sections.append("## Sleep (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Sleep section: %s", e)

    # Exercise - last 3d
    try:
        exercise = get_recent_exercise(days_back=3)
        if exercise:
            lines = [
                f"- [id:{e['id']}] {str(e['occurred_at'])[:10]}: {e['activity']} {e.get('duration_minutes') or '?'}min"
                f"{f' — {e.get('notes', '')[:70]}' if e.get('notes') else ''}"
                for e in exercise
            ]
            sections.append("## Exercise (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Exercise section: %s", e)

    # Journal - last 3d
    try:
        journal = get_recent_journal(days_back=3)
        if journal:
            lines = [f"- [id:{j['id']}] {str(j['logged_at'])[:10]}: {j['description'][:70]}" for j in journal[:5]]
            sections.append("## Journal (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Journal section: %s", e)

    # Recipes - names only (backend fetches nutrition automatically)
    try:
        recipes = list_recipes()
        if recipes:
            names = [r['name'] for r in recipes]
            sections.append(f"## Saved Recipes\n{', '.join(names)}")
    except Exception as e:
        logger.debug("Error building Recipes section: %s", e)

    # Nutrition summary (3d averages)
    try:
        summary = get_nutrition_summary(days=3)
        if summary and summary not in ("No nutrition data to analyze", "No nutrition summary"):
            sections.append(summary)
    except Exception as e:
        logger.debug("Error building Nutrition summary section: %s", e)

    # Nutrition alerts (3d rolling)
    try:
        alerts = get_nutrition_alerts(days=3)
        if alerts and alerts not in ("No nutrition data to analyze", "No nutrition alerts"):
            sections.append(alerts)
    except Exception as e:
        logger.debug("Error building Nutrition alerts section: %s", e)

    return "\n\n".join(sections) if sections else "No data logged yet."


def build_static_system_prompt(profile: dict) -> str:
    """
    Build the STATIC portion of the system prompt.
    This part is cached and should not change between calls.
    """
    profile_text = json.dumps(profile, indent=2)

    return f"""You are GutAgent, a personalized dietary assistant for IBD. Warm, practical, evidence-informed.

## Patient Profile
{profile_text}

## Core Behavior

PROACTIVE LOGGING:
- User mentions: Eating → log_meal, symptom → log_symptom, vitals → log_vital, lab → log_lab, med change → log_medication_event, sleep → log_sleep, activity → log_exercise
- No permission needed. Log and confirm briefly.
- Exception: Follow-up about recent entry = correction (see CORRECTIONS)
- BP: "123/85/82" = systolic/diastolic/HR. Notes <70 chars.

NUTRITION:
- Check saved recipes first. Match → use recipe_name, quantity = servings
- No match → estimate macros + all micros (B12:μg, D:IU, folate:μg, Fe:mg, Zn:mg, Mg:mg, Ca:mg, K:mg, ω3:g, A:IU, C:mg)
- Always estimate quantity/unit if not specified (e.g., 1 cup, 150g)
- Multi-item meals → check each item for recipe match
- User provides recipe with ingredients → save_recipe with macros and all micros
- Show full breakdown when logging
- Nutrition summary/alerts: in patient data (3d) — tools only for other ranges

CORRECTIONS:
- IDs shown as [id:47]. Use ID from "Recently logged" for "update that"
- Older entries → query_logs with date_search
- Meal desc change → delete + relog (recalcs nutrition)
- Never create new entry when correction needed (except meal desc updates)

TIMESTAMPS (always set occurred_at):
- breakfast=08:00, lunch=12:30, snack=16:00, dinner=19:30
- "yesterday's lunch" → yesterday 12:30
- Multiple meals → set appropriate time for each based on type

SEVERITY: Ask 1-10, never guess.

SEPARATE CONCERNS: Meal + symptom → separate tool calls.

DIETARY GUIDANCE: Respect profile triggers/safe foods. Never suggest known triggers.

COMMUNICATION: Brief and direct. Don't be repetitive and don't regurgitate profile data.

LABS: Check dates, interpret holistically. Don't repeat old concerns.

PATTERNS & TRENDS:
- Establish baseline using query_logs historical data
- Compare current vs baseline (e.g., "baseline 118/78 in 2024, now 130/85")
- Analyze direction, variability, correlations
- Symptom → check recent meals for triggers
- Note correlations (med changes, nutrition gaps)

NEVER FABRICATE DATA: No invented meds, diagnoses, labs for this patient.

SAVE SUGGESTIONS: Offer to save clinical recs (tests, deficiency checks), not routine food tips.
"""


def build_patient_data_context() -> str:
    """Build the patient data context — cacheable, changes when user logs something."""
    patient_data = get_patient_data()
    return f"""## Current Data from Patient's Records
{patient_data}"""


def build_turn_context(recent_logs_str: str = "") -> str:
    """Build the turn context — changes every turn, never cached.

    Args:
        recent_logs_str: Formatted string of recently logged entries.
    """
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = [f"## Current Date and Time\n{today}"]

    if recent_logs_str:
        parts.append(recent_logs_str)

    return "\n\n".join(parts)

