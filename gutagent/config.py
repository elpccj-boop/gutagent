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
        "name": "query_journal",
        "description": (
            "Search the food journal and symptom log. Use to find what the user ate "
            "recently, check symptom history, or find specific foods."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "recent_meals", "recent_symptoms",
                        "food_search", "symptom_search", "date_range",
                        "recent_vitals", "recent_meds", "recent_labs"
                    ],
                    "description": "Type of query"
                },
                "search_term": {
                    "type": "string",
                    "description": "Food or symptom to search for"
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
        "name": "analyze_patterns",
        "description": (
            "Analyze correlations between foods and symptoms over time. Call when "
            "the user asks about recurring issues, what's causing symptoms, or wants "
            "to see patterns in their data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symptom_focus": {
                    "type": "string",
                    "description": "Optional: focus on a specific symptom"
                },
                "food_focus": {
                    "type": "string",
                    "description": "Optional: focus on a specific food"
                },
                "days_back": {
                    "type": "integer",
                    "description": "Days of data to analyze (default 30)"
                }
            }
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
        "name": "correct_entry",
        "description": (
            "Update or delete an existing entry. Use when the user wants to fix "
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
                    "enum": ["meals", "symptoms", "vitals", "medication_events"],
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
]
