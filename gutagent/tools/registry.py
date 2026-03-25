"""Tool registry — maps tool names to their implementations."""

import json
from gutagent.db import (
    log_meal_with_nutrition,
    log_symptom,
    log_vital,
    log_lab,
    log_medication_event,
    log_sleep,
    log_exercise,
    log_journal_entry,
    update_log,
    delete_log,
    search_meals_by_food,
    search_symptoms,
    get_recent_meals,
    get_recent_symptoms,
    get_vitals_summary,
    get_labs_by_date,
    search_labs_by_test,
    get_meds_summary,
    get_recent_sleep,
    get_recent_exercise,
    get_recent_journal,
    save_recipe,
    get_recipe,
    list_recipes,
    delete_recipe,
    get_nutrition_summary,
    get_nutrition_alerts,
    get_logs_by_date,
)

from gutagent.profile import load_profile, update_profile


# All tracked nutrients
NUTRIENTS = [
    "calories", "protein", "carbs", "fat", "fiber",
    "vitamin_b12", "vitamin_d", "folate", "iron", "zinc", "magnesium",
    "calcium", "potassium", "omega_3", "vitamin_a", "vitamin_c"
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return its result as a string."""
    
    handlers = {
        "log_meal": _handle_log_meal,
        "log_symptom": _handle_log_symptom,
        "log_vital": _handle_log_vital,
        "log_lab": _handle_log_lab,
        "log_medication_event": _handle_log_medication_event,
        "log_sleep": _handle_log_sleep,
        "log_exercise": _handle_log_exercise,
        "log_journal": _handle_log_journal,
        "correct_log": _handle_correct_log,
        "query_logs": _handle_query_logs,
        "get_profile": _handle_get_profile,
        "update_profile": _handle_update_profile,
        "save_recipe": _handle_save_recipe,
        "get_recipe": _handle_get_recipe,
        "list_recipes": _handle_list_recipes,
        "delete_recipe": _handle_delete_recipe,
        "get_nutrition_summary": _handle_get_nutrition_summary,
        "get_nutrition_alerts": _handle_get_nutrition_alerts,
    }
    
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    try:
        result = handler(tool_input)
        # Most handlers return dicts, but query_logs returns string
        if isinstance(result, str):
            return result
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _format_log_entry(entry: dict, table: str) -> str:
    """
    Format a single log entry for compact display in query results.
    Mirrors the formatting style used in system.py dynamic context.
    """
    entry_id = entry['id']

    # Get date from various possible fields
    date_field = entry.get('occurred_at') or entry.get('test_date') or entry.get('logged_at') or ''
    date = str(date_field)[:10] if date_field else '?'

    if table == "meals":
        meal_type = entry.get('meal_type', '?')
        desc = entry['description']
        return f"[id:{entry_id}] {date} {meal_type}: {desc}"

    elif table == "symptoms":
        symptom = entry['symptom']
        severity = entry.get('severity', '?')
        return f"[id:{entry_id}] {date}: {symptom} ({severity})"

    elif table == "vitals":
        if entry.get('systolic'):
            sys = entry['systolic']
            dia = entry['diastolic']
            hr = entry.get('heart_rate', '?')
            return f"[id:{entry_id}] {date}: BP {sys}/{dia} HR:{hr}"
        else:
            vital_type = entry['vital_type']
            value = entry.get('value', '?')
            unit = entry.get('unit', '')
            return f"[id:{entry_id}] {date}: {vital_type} {value} {unit}"

    elif table == "medications":
        med = entry['medication']
        event = entry['event_type']
        return f"[id:{entry_id}] {date} {event}: {med}"

    elif table == "labs":
        test = entry['test_name']
        value = entry.get('value', '?')
        unit = entry.get('unit', '')
        status = entry.get('status', '?')
        return f"[id:{entry_id}] {date}: {test} = {value} {unit} ({status})"

    elif table == "sleep":
        hours = entry.get('hours', '?')
        quality = entry.get('quality', '')
        return f"[id:{entry_id}] {date}: {hours}h {quality}"

    elif table == "exercise":
        activity = entry['activity']
        duration = entry.get('duration_minutes', '?')
        return f"[id:{entry_id}] {date}: {activity} {duration}min"

    elif table == "journal":
        desc = entry['description'][:50]
        return f"[id:{entry_id}] {date}: {desc}"

    else:
        return f"[id:{entry_id}] {date}: {str(entry)[:50]}"


def _handle_log_meal(input: dict) -> dict:
    """Log a meal with nutrition data from Claude's estimates or recipes."""
    items = input.get("items", [])

    # Sum up nutrition from all items (recipes or estimates)
    nutrition = {nutrient: 0 for nutrient in NUTRIENTS}
    meal_items = []

    for item in items:
        item_recipe_name = item.get("recipe_name")

        # If item has a recipe, use recipe nutrition × quantity
        if item_recipe_name:
            recipe = get_recipe(item_recipe_name)
            if recipe and recipe.get("nutrition"):
                quantity = item.get("quantity", 1)
                # Multiply recipe nutrition by quantity
                for nutrient in NUTRIENTS:
                    nutrition[nutrient] += recipe["nutrition"].get(nutrient, 0) * quantity

                # Store recipe item
                meal_items.append({
                    "food_name": f"{item_recipe_name} (recipe)",
                    "quantity": quantity,
                    "unit": item.get("unit", "serving"),
                })
                continue

        # Otherwise use provided nutrition estimates
        for nutrient in NUTRIENTS:
            nutrition[nutrient] += item.get(nutrient, 0)

        # Build meal item record
        meal_items.append({
            "food_name": item.get("name", "unknown"),
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
        })

    # Log meal with nutrition
    return log_meal_with_nutrition(
        meal_type=input.get("meal_type"),
        description=input["description"],
        items=meal_items,
        nutrition=nutrition,
        occurred_at=input.get("occurred_at"),
    )


def _handle_log_symptom(input: dict) -> dict:
    return log_symptom(
        symptom=input["symptom"],
        severity=input["severity"],
        timing=input.get("timing"),
        notes=input.get("notes"),
        occurred_at=input.get("occurred_at"),
    )


def _handle_log_vital(input: dict) -> dict:
    return log_vital(
        vital_type=input["vital_type"],
        systolic=input.get("systolic"),
        diastolic=input.get("diastolic"),
        heart_rate=input.get("heart_rate"),
        value=input.get("value"),
        unit=input.get("unit"),
        occurred_at=input.get("occurred_at"),
        notes=input.get("notes"),
    )


def _handle_log_lab(input: dict) -> dict:
    return log_lab(
        test_name=input["test_name"],
        test_date=input.get("test_date"),
        value=input.get("value"),
        unit=input.get("unit"),
        reference_range=input.get("reference_range"),
        status=input.get("status"),
        notes=input.get("notes"),
    )


def _handle_log_medication_event(input: dict) -> dict:
    return log_medication_event(
        medication=input["medication"],
        event_type=input["event_type"],
        occurred_at=input.get("occurred_at"),
        dose=input.get("dose"),
        notes=input.get("notes"),
    )


def _handle_log_sleep(input: dict) -> dict:
    return log_sleep(
        hours=input.get("hours"),
        quality=input.get("quality"),
        occurred_at=input.get("occurred_at"),
        notes=input.get("notes"),
    )


def _handle_log_exercise(input: dict) -> dict:
    return log_exercise(
        activity=input["activity"],
        duration_minutes=input.get("duration_minutes"),
        occurred_at=input.get("occurred_at"),
        notes=input.get("notes"),
    )


def _handle_log_journal(input: dict) -> dict:
    return log_journal_entry(
        description=input["description"],
    )


def _handle_correct_log(input: dict) -> dict:
    if input["action"] == "delete":
        return delete_log(input["table"], input["entry_id"])
    else:
        return update_log(input["table"], input["entry_id"], input.get("updates", {}))


def _handle_query_logs(input: dict) -> str:
    """
    Query historical data and return compact string format.

    Returns string instead of dict to minimize tokens in tool_result messages.
    Format mirrors system.py dynamic context for consistency.
    """
    query_type = input["query_type"]
    days_back = input.get("days_back", 7)
    search_term = input.get("search_term", "")

    # Map query types to their handler functions and table names
    simple_queries = {
        "recent_meals": (get_recent_meals, "meals"),
        "recent_symptoms": (get_recent_symptoms, "symptoms"),
        "recent_sleep": (get_recent_sleep, "sleep"),
        "recent_exercise": (get_recent_exercise, "exercise"),
        "recent_journal": (get_recent_journal, "journal"),
    }

    # Handle simple "recent_X" queries
    if query_type in simple_queries:
        func, table = simple_queries[query_type]
        entries = func(days_back)

        if not entries:
            return f"No {table} entries found in last {days_back} days"

        lines = [_format_log_entry(e, table) for e in entries]
        return f"{len(entries)} {table} (last {days_back}d):\n" + "\n".join(lines)

    # Handle meds (default to all history, returns summary like vitals)
    elif query_type == "recent_meds":
        days = input.get("days_back", 0)
        return get_meds_summary(days)

    # Handle vitals (special case - returns pre-formatted string from model)
    elif query_type == "recent_vitals":
        vital_type = input.get("search_term")
        days = input.get("days_back", 0)
        # get_vitals_summary returns formatted string
        return get_vitals_summary(days, vital_type)

    # Handle labs - search_term can be a date (YYYY-MM-DD) or test name
    elif query_type == "recent_labs":
        import re
        if search_term and re.match(r'^\d{4}-\d{2}-\d{2}$', search_term):
            # It's a date
            labs = get_labs_by_date(search_term)
            if not labs:
                return f"No lab results found for date {search_term}"
            lines = [_format_log_entry(lab, "labs") for lab in labs]
            return f"{len(labs)} lab results from {search_term}:\n" + "\n".join(lines)
        elif search_term:
            # It's a test name
            labs = search_labs_by_test(search_term)
            if not labs:
                return f"No lab results found for test '{search_term}'"
            lines = [_format_log_entry(lab, "labs") for lab in labs]
            return f"{len(labs)} results for '{search_term}':\n" + "\n".join(lines)
        else:
            # No search term - get most recent date
            labs = get_labs_by_date()
            if not labs:
                return "No lab results found"
            lines = [_format_log_entry(lab, "labs") for lab in labs]
            return f"{len(labs)} lab results (most recent):\n" + "\n".join(lines)

    # Handle search queries
    elif query_type == "food_search":
        if not search_term:
            return "Error: search_term required for food_search"

        meals = search_meals_by_food(search_term)
        if not meals:
            return f"No meals found containing '{search_term}'"

        lines = [_format_log_entry(m, "meals") for m in meals]
        return f"{len(meals)} meals with '{search_term}':\n" + "\n".join(lines)

    elif query_type == "symptom_search":
        if not search_term:
            return "Error: search_term required for symptom_search"

        symptoms = search_symptoms(search_term)
        if not symptoms:
            return f"No symptoms found matching '{search_term}'"

        lines = [_format_log_entry(s, "symptoms") for s in symptoms]
        return f"{len(symptoms)} '{search_term}' symptoms:\n" + "\n".join(lines)

    # Handle date-based queries
    elif query_type == "date_search":
        date = input.get("date")
        table = input.get("table", "meals")

        if not date:
            return "Error: date parameter required for date_search (YYYY-MM-DD format)"

        entries = get_logs_by_date(table, date)
        if not entries:
            return f"No {table} entries found on {date}"

        lines = [_format_log_entry(e, table) for e in entries]
        return f"{len(entries)} {table} on {date}:\n" + "\n".join(lines)

    elif query_type == "date_range":
        # Get both meals and symptoms for the date range
        meals = get_recent_meals(days_back)
        symptoms = get_recent_symptoms(days_back)

        result_lines = []

        if meals:
            meal_lines = [_format_log_entry(m, "meals") for m in meals]
            result_lines.append(f"{len(meals)} meals (last {days_back}d):\n" + "\n".join(meal_lines))

        if symptoms:
            symptom_lines = [_format_log_entry(s, "symptoms") for s in symptoms]
            result_lines.append(f"{len(symptoms)} symptoms (last {days_back}d):\n" + "\n".join(symptom_lines))

        if not result_lines:
            return f"No meals or symptoms found in last {days_back} days"

        return "\n\n".join(result_lines)

    return f"Error: Unknown query type '{query_type}'"


def _handle_get_profile(input: dict) -> dict:
    return load_profile()


def _handle_update_profile(input: dict) -> dict:
    return update_profile(
        section=input["section"],
        action=input["action"],
        value=input["value"],
    )


def _handle_save_recipe(input: dict) -> dict:
    return save_recipe(
        name=input["name"],
        ingredients=input["ingredients"],
        notes=input.get("notes"),
        servings=input.get("servings", 1),
    )


def _handle_get_recipe(input: dict) -> dict:
    recipe = get_recipe(input["name"])
    if recipe:
        return recipe
    return {"error": f"Recipe not found: {input['name']}"}


def _handle_list_recipes(input: dict) -> dict:
    recipes = list_recipes()
    return {"recipes": recipes, "count": len(recipes)}


def _handle_delete_recipe(input: dict) -> dict:
    return delete_recipe(input["name"])


def _handle_get_nutrition_summary(input: dict) -> str:
    days = input.get("days", 3)
    return get_nutrition_summary(days)


def _handle_get_nutrition_alerts(input: dict) -> str:
    days = input.get("days", 3)
    return get_nutrition_alerts(days)
