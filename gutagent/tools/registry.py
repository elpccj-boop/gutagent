"""Tool registry — maps tool names to their implementations."""

import json
from gutagent.db.models import (
    log_meal as db_log_meal,
    log_symptom as db_log_symptom,
    log_medication_event as db_log_medication_event,
    log_vital as db_log_vital,
    update_log as db_update_log,
    delete_log as db_delete_log,
    get_recent_meals,
    get_recent_symptoms,
    search_meals_by_food,
    search_symptoms,
    get_recent_vitals,
    get_recent_meds,
    get_recent_labs,
    log_sleep,
    get_recent_sleep,
    log_exercise,
    get_recent_exercise,
    log_journal_entry,
    get_recent_journal,
)

from gutagent.profile import load_profile, update_profile

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return its result as a string."""
    print(f"[TOOL CALL] {tool_name}: {tool_input}")
    
    handlers = {
        "log_meal": _handle_log_meal,
        "log_symptom": _handle_log_symptom,
        "log_medication_event": _handle_log_medication_event,
        "log_vital": _handle_log_vital,
        "correct_log": _handle_correct_log,
        "query_logs": _handle_query_logs,
        "get_profile": _handle_get_profile,
        "update_profile": _handle_update_profile,
        "log_sleep": _handle_log_sleep,
        "log_exercise": _handle_log_exercise,
        "log_journal": _handle_log_journal,
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

def _handle_correct_log(input: dict) -> dict:
    if input["action"] == "delete":
        return db_delete_log(input["table"], input["entry_id"])
    else:
        return db_update_log(input["table"], input["entry_id"], input.get("updates", {}))

def _handle_query_logs(input: dict) -> dict:
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

    elif query_type == "recent_sleep":
        days = input.get("days_back", 7)
        entries = get_recent_sleep(days)
        return {"sleep": entries, "count": len(entries)}

    elif query_type == "recent_exercise":
        days = input.get("days_back", 7)
        entries = get_recent_exercise(days)
        return {"exercise": entries, "count": len(entries)}

    elif query_type == "recent_journal":
        days = input.get("days_back", 7)
        entries = get_recent_journal(days)
        return {"journal": entries, "count": len(entries)}

    return {"error": f"Unknown query type: {query_type}"}

def _handle_get_profile(input: dict) -> dict:
    return load_profile()

def _handle_update_profile(input: dict) -> dict:
    return update_profile(
        section=input["section"],
        action=input["action"],
        value=input["value"],
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
        occurred_at=input.get("occurred_at"),
    )
