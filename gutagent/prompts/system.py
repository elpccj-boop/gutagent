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
    get_nutrition_alerts,
)
from gutagent.logging_config import get_logger

logger = get_logger("prompts")


def get_dynamic_context() -> str:
    """Pull recent data from all tables for the system prompt."""
    sections = []

    # Medications - current + recent 30 days
    try:
        meds = get_current_and_recent_meds(recent_days=30)
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
                f"- {lab['test_name']}: "
                f"{f'{lab.get('value')} {lab.get('unit', '')}' if lab.get('value') else '—'}"
                f"{f' (ref: {lab.get('reference_range')})' if lab.get('reference_range') else ''}"
                f"{f' [{lab['status']}]' if lab.get('status') else ''}"
                f"{f' — {lab.get('notes', '')[:70]}' if lab.get('notes') else ''}"
                for lab in labs
            ]
            sections.append("## Labs (Latest)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Labs section: %s", e)

    # Vitals - last 7d (get_recent_vitals returns pre-formatted string)
    try:
        vitals_text = get_recent_vitals(days_back=7)
        if vitals_text:
            sections.append(vitals_text)
    except Exception as e:
        logger.debug("Error building Vitals section: %s", e)

    # Meals - last 3d
    try:
        meals = get_recent_meals(days_back=3)
        if meals:
            lines = [
                f"- [id:{m['id']}] {m['occurred_at']}: {m.get('meal_type') or 'meal'} — {m['description']}"
                f"{f' [{int(m['calories'])}cal {int(m.get('protein', 0))}p {int(m.get('carbs', 0))}c {int(m.get('fat', 0))}f {int(m.get('fiber', 0))}fib]' if m.get('calories') else ''}"
                for m in meals
            ]
            sections.append("## Meals (3d)\n" + "\n".join(lines))
    except Exception as e:
        logger.debug("Error building Meals section: %s", e)

    # Symptoms - last 7d
    try:
        symptoms = get_recent_symptoms(days_back=7)
        if symptoms:
            lines = [
                f"- [id:{s['id']}] {s['occurred_at']}: {s['symptom']} ({s['severity']})"
                f"{f' — {s.get('notes', '')[:70]}' if s.get('notes') else ''}"
                for s in symptoms
            ]
            sections.append("## Symptoms (7d)\n" + "\n".join(lines))
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

    # Recipes - with per-serving nutrition
    try:
        recipes = list_recipes()
        if recipes:
            lines = ["## Recipes (per serving)"]
            for r in recipes:
                nutr = r.get('nutrition', {})

                cal = int(nutr.get('calories') or 0)
                pro = int(nutr.get('protein') or 0)
                carb = int(nutr.get('carbs') or 0)
                fat = int(nutr.get('fat') or 0)
                macros = f"{cal}cal {pro}p {carb}c {fat}f"

                micros = []
                if nutr.get('vitamin_b12'): micros.append(f"B12:{nutr['vitamin_b12']:.1f}")
                if nutr.get('vitamin_d'): micros.append(f"D:{int(nutr['vitamin_d'])}")
                if nutr.get('iron'): micros.append(f"Fe:{nutr['iron']:.1f}")
                if nutr.get('calcium'): micros.append(f"Ca:{int(nutr['calcium'])}")
                if nutr.get('omega_3'): micros.append(f"ω3:{nutr['omega_3']:.1f}")
                if nutr.get('folate'): micros.append(f"fol:{int(nutr['folate'])}")
                if nutr.get('zinc'): micros.append(f"Zn:{nutr['zinc']:.1f}")
                if nutr.get('magnesium'): micros.append(f"Mg:{int(nutr['magnesium'])}")
                if nutr.get('potassium'): micros.append(f"K:{int(nutr['potassium'])}")
                if nutr.get('vitamin_a'): micros.append(f"A:{int(nutr['vitamin_a'])}")
                if nutr.get('vitamin_c'): micros.append(f"C:{int(nutr['vitamin_c'])}")
                if nutr.get('fiber'): micros.append(f"fib:{int(nutr['fiber'])}")

                micro_str = " ".join(micros) if micros else ""
                srv = r.get('servings') or 1
                servings = int(srv) if srv == int(srv) else srv
                lines.append(f"- {r['name']} ({servings}srv): {macros} | {micro_str}")
            sections.append("\n".join(lines))
    except Exception as e:
        logger.debug("Error building Recipes section: %s", e)

    return "\n\n".join(sections) if sections else "No data logged yet."


def get_nutrition_alerts_text() -> str:
    """Get formatted nutrition alerts for the system prompt."""
    try:
        alerts = get_nutrition_alerts(days=3)
    except Exception as e:
        return ""

    if not alerts or alerts == "No nutrition data to analyze" or alerts == "No nutrition alerts":
        return ""

    return alerts


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

ANALYZING PATTERNS & TRENDS:
- Establish baseline using query_logs historical data
- Compare current vs baseline (e.g., "baseline 118/78 in 2024, now 130/85")
- Analyze direction, variability, correlations
- Symptom reported → check recent meals via query_logs
- Note correlations (med changes, nutrition gaps, timing)
- Flag potential triggers

NEVER FABRICATE DATA: No invented meds, diagnoses, labs for this patient.

SAVE SUGGESTIONS: Offer to save clinical recs (tests, deficiency checks), not routine food tips.
"""


def build_dynamic_context() -> str:
    """Build the DYNAMIC portion of the system prompt (not cached)."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    dynamic_context = get_dynamic_context()
    nutrition_alerts = get_nutrition_alerts_text()

    return f"""## Current Date and Time
{today}

## Current Data from Patient's Records
{dynamic_context}

{nutrition_alerts}"""

