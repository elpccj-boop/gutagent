"""Configuration and tool definitions for GutAgent."""

import os

# Model config
MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096

# API key — set via environment variable
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gutagent.db")
PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profile.json")

# Tool definitions for Claude function calling
TOOLS = [
    {
        "name": "log_meal",
        "description": (
            "Log a meal the user has eaten. Call this proactively whenever the user "
            "mentions eating something, even casually. Extract individual foods from "
            "their natural language description."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "meal_type": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                    "description": "Type of meal. Infer from time of day or context if not stated."
                },
                "description": {
                    "type": "string",
                    "description": "Natural language description of the meal"
                },
                "foods": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Individual foods/ingredients extracted from the description"
                },
                "occurred_at": {
                    "type": "string",
                    "description": (
                        "When the meal actually happened, in YYYY-MM-DD HH:MM:SS format. "
                        "Infer from context — 'yesterday lunch' becomes yesterday's date at 12:30, "
                        "'this morning' becomes today at 08:00, etc. "
                        "Leave out if the meal is happening right now."
                    )
                },
            },
            "required": ["description", "foods"]
        }
    },
    {
        "name": "log_symptom",
        "description": (
            "Log a symptom the user is experiencing. Call this proactively whenever "
            "the user mentions ANY physical or mental symptom, even casually — "
            "'I'm tired', 'stomach hurts', 'feeling bloated', 'brain fog', 'irritable'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "description": (
                        "The symptom: bloating, fatigue, pain, brain_fog, nausea, "
                        "diarrhea, constipation, mood_change, tingling, headache, "
                        "lethargy, irritability, heartburn, etc."
                    )
                },
                "severity": {
                    "type": "integer",
                    "description": "Severity 1-10. Ask the user if unclear."
                },
                "timing": {
                    "type": "string",
                    "description": "When relative to last meal or time of day"
                },
                "notes": {
                    "type": "string",
                    "description": "Any additional context"
                },
                "occurred_at": {
                    "type": "string",
                    "description": (
                        "When the symptom actually occurred, in YYYY-MM-DD HH:MM:SS format. "
                        "Infer from context — 'last night' becomes yesterday's date at 21:00, "
                        "'after lunch today' becomes today at 13:30, etc. "
                        "Leave out if the symptom is happening right now."
                    )
                },
            },
            "required": ["symptom", "severity"]
        }
    },
    {
        "name": "log_medication_event",
        "description": (
            "Log a medication change — starting, stopping, or changing dose. "
            "Call this whenever the user mentions any change in medication."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "medication": {
                    "type": "string",
                    "description": "Name of the medication"
                },
                "event_type": {
                    "type": "string",
                    "enum": ["started", "stopped", "dose_changed", "side_effect", "snapshot"],
                    "description": "What happened with the medication"
                },
                "occurred_at": {
                    "type": "string",
                    "description": (
                        "When this happened, in YYYY-MM-DD HH:MM:SS format. "
                        "Infer from context. Leave out if happening right now."
                    )
                },
                "dose": {
                    "type": "string",
                    "description": "Dose information if relevant"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional context"
                }
            },
            "required": ["medication", "event_type"]
        }
    },
    {
        "name": "log_vital",
        "description": (
            "Log a vital sign reading — blood pressure, weight, temperature, etc. "
            "Call this whenever the user mentions any measurement or reading."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vital_type": {
                    "type": "string",
                    "enum": ["blood_pressure", "weight", "temperature", "blood_sugar", "oxygen_saturation"],
                    "description": "Type of vital sign"
                },
                "systolic": {
                    "type": "integer",
                    "description": "Systolic blood pressure (top number). Only for blood_pressure."
                },
                "diastolic": {
                    "type": "integer",
                    "description": "Diastolic blood pressure (bottom number). Only for blood_pressure."
                },
                "heart_rate": {
                    "type": "integer",
                    "description": "Heart rate in bpm. Often measured with blood pressure."
                },
                "value": {
                    "type": "number",
                    "description": "Numeric value for non-BP vitals (weight in kg/lb, temp in F/C, etc.)"
                },
                "unit": {
                    "type": "string",
                    "description": "Unit of measurement — kg, lb, F, C, mg/dL, %, etc."
                },
                "occurred_at": {
                    "type": "string",
                    "description": (
                        "When the reading was taken, in YYYY-MM-DD HH:MM:SS format. "
                        "Infer from context. Leave out if taken right now."
                    )
                },
                "notes": {
                    "type": "string",
                    "description": "Additional context — position, time of day, before/after medication, etc."
                }
            },
            "required": ["vital_type"]
        }
    },
    {
        "name": "query_logs",
        "description": (
            "Search logged data — meals, symptoms, vitals, medications, labs. "
            "Use to check history, find patterns, or look up specific entries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "recent_meals", "recent_symptoms", "food_search",
                        "symptom_search", "date_range", "recent_vitals",
                        "recent_meds", "recent_labs", "recent_sleep",
                        "recent_exercise","recent_journal"
                    ],
                    "description": "Type of query"
                },
                "search_term": {
                    "type": "string",
                    "description": "Search filter — food name, symptom type, vital type, or lab test date depending on query_type"
                },
                "days_back": {
                    "type": "integer",
                    "description": "How many days back to search. Default 7 for meals/symptoms. For vitals, meds, and labs, omit this to get ALL historical data."
                }
            },
            "required": ["query_type"]
        }
    },
    {
        "name": "get_profile",
        "description": "Retrieve the user's full medical profile.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "correct_log",
        "description": (
            "Update or delete an existing log entry. Use when the user wants to fix "
            "a value (like severity, timestamp, description) or remove a duplicate. "
            "Never create a new entry when a correction is needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["update", "delete"],
                    "description": "Whether to update fields or delete the entry"
                },
                "table": {
                    "type": "string",
                    "enum": ["meals", "symptoms", "vitals", "medication_events", "sleep", "exercise", "journal"],
                    "description": "Which table the entry is in"
                },
                "entry_id": {
                    "type": "integer",
                    "description": "The id of the entry to correct"
                },
                "updates": {
                    "type": "object",
                    "description": "Fields to update with new values. Only for action=update. Use column names: severity, occurred_at, description, notes, symptom, meal_type, foods, systolic, diastolic, heart_rate, medication, event_type, dose, etc."
                }
            },
            "required": ["action", "table", "entry_id"]
        }
    },
    {
        "name": "update_profile",
        "description": (
            "Add, update, or remove information in the user's medical profile. Use when "
            "the user shares permanent facts about themselves — chronic conditions, baseline "
            "traits, dietary preferences, family history, etc. This persists across sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": (
                        "Dot-notation path to the section to update. Examples: "
                        "'conditions.chronic', 'conditions.other', 'dietary.triggers', "
                        "'dietary.safe_foods', 'lifestyle.notes', 'family_history.notes', "
                        "'personal.notes'"
                    )
                },
                "action": {
                    "type": "string",
                    "enum": ["append", "set", "remove"],
                    "description": (
                        "append: add to a list. "
                        "set: replace a value (string or list). "
                        "remove: remove an item from a list (matches by substring)."
                    )
                },
                "value": {
                    "type": "string",
                    "description": "The value to add, set, or remove"
                }
            },
            "required": ["section", "action", "value"]
        }
    },
    {
        "name": "log_sleep",
        "description": (
            "Log sleep information. Use when the user mentions how they slept — "
            "hours, quality, or both."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "number",
                    "description": "Hours of sleep"
                },
                "quality": {
                    "type": "string",
                    "description": "Sleep quality — good, poor, interrupted, restless, deep, etc."
                },
                "occurred_at": {
                    "type": "string",
                    "description": (
                        "The night of sleep, in YYYY-MM-DD HH:MM:SS format. "
                        "Use the date the user went to bed. Leave out if last night."
                    )
                },
                "notes": {
                    "type": "string",
                    "description": "Additional context — woke up multiple times, dreams, etc."
                }
            }
        }
    },
    {
        "name": "log_exercise",
        "description": (
            "Log exercise or physical activity. Use when the user mentions "
            "walking, hiking, gym, yoga, or any physical activity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "activity": {
                    "type": "string",
                    "description": "Type of activity — walk, hike, gym, yoga, run, swim, etc."
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration in minutes"
                },
                "occurred_at": {
                    "type": "string",
                    "description": (
                        "When the exercise happened, in YYYY-MM-DD HH:MM:SS format. "
                        "Leave out if just now."
                    )
                },
                "notes": {
                    "type": "string",
                    "description": "Additional context — intensity, location, how it felt"
                }
            },
            "required": ["activity"]
        }
    },
    {
        "name": "log_journal",
        "description": (
            "Log a freeform journal entry. Use when the user wants to note something "
            "that isn't a meal, symptom, vital, medication, sleep, or exercise — "
            "life events, context, thoughts, or anything they want to record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What the user wants to record"
                },
                "occurred_at": {
                    "type": "string",
                    "description": "When this happened, in YYYY-MM-DD HH:MM:SS format. Leave out if now."
                }
            },
            "required": ["description"]
        }
    },
]
