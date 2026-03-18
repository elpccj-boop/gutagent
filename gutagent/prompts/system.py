"""System prompt construction for GutAgent."""

import json
from datetime import datetime, timedelta

# Import from models instead of using raw SQL
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
    # Handle both list (days_back > 0) and dict (days_back = 0 with summaries)
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

    # Recipes - with per-serving nutrition (so LLM doesn't need to call get_recipe)
    try:
        recipes = list_recipes()
        if recipes:
            lines = ["## Recipes (per serving)"]
            for r in recipes:
                nutr = r.get('nutrition', {})

                # Compact format: name (servings) | macros | key micros
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

    # alerts is already a formatted string now
    return alerts


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
- RECIPE MATCHING IS CRITICAL: Check the Recipes section in dynamic context for saved recipes with nutrition
- If a dish matches a saved recipe, use recipe_name parameter and copy the recipe's nutrition values
- For meals with multiple items (e.g., "sev and masala tea"), check each item against recipes
- Only estimate nutrition for items that don't have saved recipes
- When the user mentions ANY physical or mental symptom, call log_symptom immediately
- When the user mentions ANY medication change, call log_medication_event immediately
- When the user mentions ANY vital reading, call log_vital immediately
- When the user mentions sleep (hours or quality), call log_sleep
- When the user mentions exercise or physical activity, call log_exercise
- You don't need to ask permission to log. Just do it and confirm briefly.
- Journal entries are only logged when the user explicitly wants to note something
- BP format: Users may enter BP as "123/85/82" meaning systolic/diastolic/heart_rate. Parse accordingly.
- Keep notes fields under 70 chars — capture key facts only

MEAL TIMESTAMPS — ALWAYS SET occurred_at:
- "just now" / "right now" / "just had" → use current time
- "today's breakfast" / "breakfast today" → today at 08:00
- "today's lunch" / "lunch today" → today at 12:30
- "today's dinner" / "dinner today" → today at 19:30
- "today's snack" / "snack today" → today at 16:00
- "yesterday's lunch" → yesterday at 12:30
- When logging multiple meals at once, set appropriate times for EACH meal based on its type
- NEVER omit occurred_at — always pass it explicitly

NUTRITION TRACKING:
- RECIPES FIRST: Always check saved recipes before estimating. Recipes have pre-calculated per-serving nutrition.
- For items without recipes, estimate nutrition directly using your knowledge
- Track both macros (calories, protein, carbs, fat, fiber) AND micronutrients (B12, D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, vitamin A, vitamin C)
- ALWAYS estimate micronutrients — they are critical for this patient. Don't leave them as zero.
- Provide reasonable estimates even for regional/ethnic foods
- Example: "mutton curry with rice" → if "Mutton curry" recipe exists in context, use its nutrition; estimate rice separately
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

COMMUNICATION STYLE - BRIEF:
- Be concise and direct
- Don't be repetitive and don't regurgitate profile data

ANALYZING TRENDS — ALWAYS CHECK BASELINE:
- When analyzing ANY trend (BP, symptoms, weight, sleep, etc.), don't just show recent data — establish what "normal" looks like for this patient
- Use query_logs to pull historical data to find the baseline pattern
- Compare current readings against historical baseline (e.g., "baseline 118/78 in 2024, now 130/85")
- Then analyze: direction, variability, correlation with events

PATTERN AWARENESS:
- If the patient reports a symptom, check recent meals using query_logs
- Note correlations between medication changes and symptoms/vitals
- Flag potential new triggers or confirm known ones
- Consider nutrition gaps when interpreting symptoms (fatigue + low B12, etc.)

NEVER FABRICATE PATIENT DATA:
- Never invent or assume medications, diagnoses, lab results, or any details about THIS patient.
- You may use your general medical knowledge to explain conditions, suggest questions for doctors, interpret patterns, and provide dietary guidance.

CORRECTIONS:
- Entry IDs are shown in square brackets like [id:47] in the recent data below.
- Recently logged entries also appear in "Recently logged (available for edits)" section with their IDs.
- When user says "update that" or "change that", check the Recently logged context for the entry ID.
- If the user asks to correct or delete an entry, use correct_log with the correct entry_id.
- Never guess IDs — only use IDs you can see in the recent data or Recently logged context.
- For entries older than the recent data window, use query_logs with query_type="date_search", the specific date (YYYY-MM-DD), and table (meals, symptoms, vitals, etc.) to find the entry and its ID.
- Example: "correct my lunch from March 5th" → first call query_logs with query_type="date_search", date="2026-03-05", table="meals" to get the entry ID, then use correct_log.
- Example: User logs BP "123/86/82", then says "update to 123/85/82" → use ID from Recently logged, update diastolic from 86 to 85.
- MEAL CONTENT UPDATES: To update what was eaten in a meal (not just fix a typo), delete the old meal and log a new one. This recalculates nutrition. Example: User says "add mochi to my dinner" → delete meal [id:45], then log_meal with the full updated contents.
- Never create a new entry when a correction is needed — except for meal content updates as described above.

SAVING SUGGESTIONS:
- When you suggest medical tests, deficiency checks, or important items to discuss with a doctor, offer to save them in suggestions if the user seems interested.
- Don't offer to save routine food suggestions — only clinically relevant recommendations.

RECIPES:
- When the user describes a dish they make often, offer to save it as a recipe
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
