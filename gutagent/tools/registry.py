"""Tool registry — maps tool names to their implementations."""

import json
from gutagent.db.models import (
    log_meal as db_log_meal,
    log_symptom as db_log_symptom,
    log_medication_event as db_log_medication_event,
    log_vital as db_log_vital,
    update_entry as db_update_entry,
    delete_entry as db_delete_entry,
    get_recent_meals,
    get_recent_symptoms,
    search_meals_by_food,
    search_symptoms,
    analyze_food_symptom_patterns,
    get_recent_vitals,
    get_recent_meds,
    get_recent_labs,
)

from gutagent.profile import load_profile

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return its result as a string."""
    
    handlers = {
        "log_meal": _handle_log_meal,
        "log_symptom": _handle_log_symptom,
        "log_medication_event": _handle_log_medication_event,
        "log_vital": _handle_log_vital,
        "correct_entry": _handle_correct_entry,
        "query_journal": _handle_query_journal,
        "analyze_patterns": _handle_analyze_patterns,
        "get_profile": _handle_get_profile,
    }
    
    handler = handlers.get(tool_name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    
    try:
        result = handler(tool_input)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def _handle_log_meal(input: dict) -> dict:
    return db_log_meal(
        meal_type=input.get("meal_type"),
        description=input["description"],
        foods=input.get("foods", []),
        notes=input.get("notes"),
        occurred_at=input.get("occurred_at"),
    )

def _handle_log_symptom(input: dict) -> dict:
    return db_log_symptom(
        symptom=input["symptom"],
        severity=input["severity"],
        timing=input.get("timing"),
        notes=input.get("notes"),
        occurred_at=input.get("occurred_at"),
    )

def _handle_log_medication_event(input: dict) -> dict:
    return db_log_medication_event(
        medication=input["medication"],
        event_type=input["event_type"],
        occurred_at=input.get("occurred_at"),
        dose=input.get("dose"),
        notes=input.get("notes"),
    )

def _handle_log_vital(input: dict) -> dict:
    return db_log_vital(
        vital_type=input["vital_type"],
        systolic=input.get("systolic"),
        diastolic=input.get("diastolic"),
        heart_rate=input.get("heart_rate"),
        value=input.get("value"),
        unit=input.get("unit"),
        occurred_at=input.get("occurred_at"),
        notes=input.get("notes"),
    )

def _handle_correct_entry(input: dict) -> dict:
    if input["action"] == "delete":
        return db_delete_entry(input["table"], input["entry_id"])
    else:
        return db_update_entry(input["table"], input["entry_id"], input.get("updates", {}))

def _handle_query_journal(input: dict) -> dict:
    print(f"[DEBUG query_journal] {input}")
    query_type = input["query_type"]
    days_back = input.get("days_back", 7)
    search_term = input.get("search_term", "")

    if query_type == "recent_meals":
        meals = get_recent_meals(days_back)
        return {"meals": meals, "count": len(meals)}

    elif query_type == "recent_symptoms":
        symptoms = get_recent_symptoms(days_back)
        return {"symptoms": symptoms, "count": len(symptoms)}

    elif query_type == "food_search":
        meals = search_meals_by_food(search_term)
        return {"meals": meals, "count": len(meals), "search": search_term}

    elif query_type == "symptom_search":
        symptoms = search_symptoms(search_term)
        return {"symptoms": symptoms, "count": len(symptoms), "search": search_term}

    elif query_type == "date_range":
        meals = get_recent_meals(days_back)
        symptoms = get_recent_symptoms(days_back)
        return {"meals": meals, "symptoms": symptoms, "days": days_back}

    elif query_type == "recent_vitals":
        vital_type = input.get("search_term")
        days = input.get("days_back", 0)
        vitals = get_recent_vitals(days, vital_type)
        return {"vitals": vitals, "count": len(vitals)}

    elif query_type == "recent_meds":
        meds = get_recent_meds(days_back)
        return {"medication_events": meds, "count": len(meds)}

    elif query_type == "recent_labs":
        labs = get_recent_labs(input.get("search_term"))
        return {"labs": labs, "count": len(labs)}

    return {"error": f"Unknown query type: {query_type}"}

def _handle_analyze_patterns(input: dict) -> dict:
    return analyze_food_symptom_patterns(
        days_back=input.get("days_back", 30),
        symptom_focus=input.get("symptom_focus"),
        food_focus=input.get("food_focus"),
    )

def _handle_get_profile(input: dict) -> dict:
    return load_profile()
