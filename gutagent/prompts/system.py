"""System prompt construction for GutAgent."""

import json
from datetime import datetime, timedelta

from gutagent.db.models import (
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


def format_vitals_for_context(vitals_data) -> str:
    """Format vitals data for the dynamic context."""
    if isinstance(vitals_data, dict):
        recent = vitals_data.get("recent_30_days", [])[:10]
    else:
        recent = vitals_data[:10] if vitals_data else []

    if not recent:
        return ""

    lines = []
    for v in recent:
        notes_str = f" — {v.get('notes', '')[:70]}" if v.get('notes') else ""
        if v.get('vital_type') == 'blood_pressure':
            lines.append(f"- [id:{v['id']}] {str(v['occurred_at'])[:10]}: {v['systolic']}/{v['diastolic']} HR:{v.get('heart_rate') or '?'}{notes_str}")
        else:
            lines.append(f"- [id:{v['id']}] {str(v['occurred_at'])[:10]}: {v['vital_type']} {v.get('value')} {v.get('unit', '')}{notes_str}")

    return "## Vitals (7d)\n" + "\n".join(lines)


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
    except Exception:
        pass

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
    except Exception:
        pass

    # Vitals - last 7d
    try:
        vitals = get_recent_vitals(days_back=7)
        vitals_section = format_vitals_for_context(vitals)
        if vitals_section:
            sections.append(vitals_section)
    except Exception:
        pass

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
    except Exception:
        pass

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
    except Exception:
        pass

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
    except Exception:
        pass

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
    except Exception:
        pass

    # Journal - last 3d
    try:
        journal = get_recent_journal(days_back=3)
        if journal:
            lines = [f"- [id:{j['id']}] {str(j['logged_at'])[:10]}: {j['description'][:70]}" for j in journal[:5]]
            sections.append("## Journal (3d)\n" + "\n".join(lines))
    except Exception:
        pass

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
    except Exception:
        pass

    return "\n\n".join(sections) if sections else "No data logged yet."


def get_nutrition_alerts_text() -> str:
    """Get formatted nutrition alerts for the system prompt."""
    try:
        alerts = get_nutrition_alerts(days=3)
    except Exception:
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

    return f"""You are GutAgent, a personalized dietary assistant for a patient with IBD. 
Warm, practical, evidence-informed — like a knowledgeable friend.

## Patient's Medical Profile
{profile_text}

## Core Behavior

PROACTIVE LOGGING:
- User mentions eating → log_meal
- User mentions symptom → log_symptom
- User mentions vitals → log_vital
- User mentions lab/test → log_lab
- User mentions med change → log_medication_event
- Sleep/exercise → log_sleep/log_exercise
- No permission needed. Log and confirm briefly.
- Exception: Follow-up about recent entry = correction (see CORRECTIONS)
- BP format: "123/85/82" = systolic/diastolic/HR
- Notes <70 chars

NUTRITION (for meals):
- RECIPES FIRST: Check saved recipes before estimating
- Recipe match → use item with recipe_name param, quantity mentioned = servings (e.g., "2 cups masala tea" = 2 servings)
- No recipe → estimate macros + micros (B12:μg, D:IU, folate:μg, iron:mg, zinc:mg, Mg:mg, Ca:mg, K:mg, ω3:g, A:IU, C:mg)
- ALWAYS estimate micros
- Multi-item meals → check each item for recipe match
- User provides recipe with ingredients → save_recipe with macros and all micros with same nutrient units
- Show full nutrition breakdown when logging (macros + micros)

CORRECTIONS:
- Entry IDs shown as [id:47] in recent data
- Recently logged entries in "Recently logged" section
- "update that" → use ID from Recently logged
- For older entries → query_logs with date_search to find ID
- MEAL DESC UPDATES: Delete old meal, log new one (recalcs nutrition)
- Never create new entry when correction needed (except meal desc updates)

MEAL TIMESTAMPS (always set occurred_at):
- "just now" → current time
- "today's breakfast" → today 08:00
- "today's lunch" → today 12:30
- "today's dinner" → today 19:30
- "today's snack" → today 16:00
- "yesterday's lunch" → yesterday 12:30
- Multiple meals → set appropriate time for each based on type
- NEVER omit occurred_at

SEVERITY: Always ask 1-10, never guess.

SEPARATE CONCERNS: Meal + symptom in one message → separate tool calls for each.

DIETARY GUIDANCE: Respect profile triggers/safe foods. Never suggest known triggers.

COMMUNICATION: Brief and direct. Don't be repetitive and don't regurgitate profile data.

ANALYZING PATTERNS & TRENDS:
- Establish baseline using query_logs historical data
- Compare current vs baseline (e.g., "baseline 118/78 in 2024, now 130/85")
- Analyze direction, variability, correlations
- Symptom reported → check recent meals via query_logs
- Note correlations (med changes, nutrition gaps, timing)
- Flag potential triggers

NEVER FABRICATE: No invented meds, diagnoses, labs for THIS patient.

SAVING SUGGESTIONS: Offer to save clinically relevant recommendations (tests, deficiency checks), not routine food suggestions.
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

