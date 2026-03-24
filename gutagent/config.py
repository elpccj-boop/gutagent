"""Configuration and tool definitions for GutAgent."""

import os

# LLM Provider config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")

# Model config per provider
MODELS = {
    "claude": {
        "default": "claude-haiku-4-5-20251001",
        "smart": "claude-sonnet-4-5-20250929",
    },
    "gemini": {
        "default": "gemini-2.5-flash",
        "smart": "gemini-2.5-pro",
    },
    "openai": {
        "default": "gpt-4o-mini",
        "smart": "gpt-4o",
    },
}

def get_model_for_tier(tier: str = "default", provider: str = None) -> str:
    """Get model name for a given tier and provider."""
    provider = provider or LLM_PROVIDER
    return MODELS.get(provider, MODELS["claude"]).get(tier, MODELS[provider]["default"])


MAX_TOKENS = 4096

# API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gutagent.db")
PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profile.json")

# Tool definitions
TOOLS = [
    {
        "name": "log_meal",
        "description": "Log meal with itemized nutrition (macros + micros). Check saved recipes first, use recipe_name if match found.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meal_type": {
                    "type": "string", "enum": ["breakfast", "lunch", "dinner", "snack"],
                    "description": "Infer from time/context if not stated."
                },
                "description": {
                    "type": "string",
                    "description": "Food items only, e.g. 'Chicken curry with rice'."
                },
                "items": {
                    "type": "array",
                    "description": "Food components with nutrition estimates.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Food name"},
                            "quantity": {"type": "number", "description": "Amount"},
                            "unit": {"type": "string", "description": "Unit (piece, g, cup, tbsp)"},
                            "recipe_name": {
                                "type": "string",
                                "description": "If matches saved recipe, specify recipe name (nutrition auto-calculated from recipe × quantity)"
                            },
                            "calories": {"type": "number"},
                            "protein": {"type": "number", "description": "g"},
                            "carbs": {"type": "number", "description": "g"},
                            "fat": {"type": "number", "description": "g"},
                            "fiber": {"type": "number", "description": "g"},
                            "vitamin_b12": {"type": "number", "description": "μg"},
                            "vitamin_d": {"type": "number", "description": "IU"},
                            "folate": {"type": "number", "description": "μg"},
                            "iron": {"type": "number", "description": "mg"},
                            "zinc": {"type": "number", "description": "mg"},
                            "magnesium": {"type": "number", "description": "mg"},
                            "calcium": {"type": "number", "description": "mg"},
                            "potassium": {"type": "number", "description": "mg"},
                            "omega_3": {"type": "number", "description": "g"},
                            "vitamin_a": {"type": "number", "description": "IU"},
                            "vitamin_c": {"type": "number", "description": "mg"},
                        },
                        "required": ["name", "calories", "protein", "carbs", "fat"]
                    }
                },
                "occurred_at": {
                    "type": "string",
                    "description": "YYYY-MM-DD HH:MM:SS. Set meal-appropriate times: breakfast=08:00, lunch=12:30, dinner=19:30, snack=16:00."
                },
            },
            "required": ["description", "items"]
        }
    },
    {
        "name": "log_symptom",
        "description": "Log symptom. Call proactively when user mentions any physical/mental symptom.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "description": "bloating, fatigue, pain, brain_fog, nausea, diarrhea, etc."
                },
                "severity": {"type": "integer", "description": "1-10. Ask if unclear."},
                "timing": {"type": "string", "description": "When relative to meal/time"},
                "notes": {"type": "string"},
                "occurred_at": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS. Infer from context."},
            },
            "required": ["symptom", "severity"]
        }
    },
    {
        "name": "log_vital",
        "description": "Log vital sign (BP, weight, temp, HR, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "vital_type": {
                    "type": "string",
                    "enum": ["blood_pressure", "weight", "temperature", "heart_rate", "oxygen_saturation", "blood_glucose"]
                },
                "value": {"type": "number", "description": "Value (omit for BP)"},
                "unit": {"type": "string", "description": "kg, °F, bpm, %, mg/dL"},
                "systolic": {"type": "integer", "description": "BP only"},
                "diastolic": {"type": "integer", "description": "BP only"},
                "heart_rate": {"type": "integer", "description": "BP optional"},
                "occurred_at": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS. Infer from context."},
                "notes": {"type": "string"}
            },
            "required": ["vital_type"]
        }
    },
    {
            "name": "log_lab",
            "description": "Log lab test results.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "test_name": {"type": "string", "description": "Test name (e.g., B12, Ferritin, CRP)"},
                    "test_date": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS. Infer from context."},
                    "value": {"type": "number"},
                    "unit": {"type": "string", "description": "pg/mL, ng/mL, mg/dL, etc."},
                    "reference_range": {"type": "string", "description": "e.g., '200-900 pg/mL'"},
                    "status": {"type": "string", "enum": ["normal", "low", "high", "critical"]},
                    "notes": {"type": "string"}
                },
                "required": ["test_name"]
            }
        },
    {
            "name": "log_medication_event",
            "description": "Log medication change (start/stop/dose change).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "medication": {"type": "string"},
                    "event_type": {"type": "string", "enum": ["started", "stopped", "dose_changed"]},
                    "occurred_at": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS. Infer from context."},
                    "dose": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["medication", "event_type"]
            }
        },
    {
            "name": "log_sleep",
            "description": "Log sleep hours and quality.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "hours": {"type": "number"},
                    "quality": {"type": "string", "description": "good, poor, interrupted, restless, deep"},
                    "occurred_at": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS. Infer from context."},
                    "notes": {"type": "string"}
                }
            }
        },
    {
        "name": "log_exercise",
        "description": "Log physical activity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "activity": {"type": "string", "description": "walk, hike, gym, yoga, run, swim"},
                "duration_minutes": {"type": "integer"},
                "occurred_at": {"type": "string", "description": "YYYY-MM-DD HH:MM:SS. Infer from context."},
                "notes": {"type": "string"}
            },
            "required": ["activity"]
        }
    },
    {
        "name": "log_journal",
        "description": "Freeform journal entry for things that don't fit other categories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "query_logs",
        "description": "Query historical data. Use for pattern analysis, finding baselines, or locating specific entries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": [
                        "recent_meals", "recent_symptoms", "recent_vitals", "recent_labs",
                        "recent_meds", "recent_sleep", "recent_exercise", "recent_journal",
                        "food_search", "symptom_search", "date_search", "date_range",
                    ],
                    "description": "Type of query. Use date_search to find entries on a specific date."
                },
                "search_term": {
                    "type": "string",
                    "description": "Search filter — food name, symptom type, vital type, or lab test date depending on query_type"
                },
                "days_back": {
                    "type": "integer",
                    "description": "How many days back to search. Default 7 for meals/symptoms. For vitals, meds, and labs, omit this to get ALL historical data."
                },
                "date": {
                    "type": "string",
                    "description": "Specific date in YYYY-MM-DD format. Required for date_search query_type."
                },
                "table": {
                    "type": "string",
                    "enum": ["meals", "symptoms", "vitals", "medications", "sleep", "exercise", "journal", "labs", "recipes"],
                    "description": "Which table to search. Used with date_search. Default is meals."
                }
            },
            "required": ["query_type"]
        }
    },
    {
        "name": "correct_log",
        "description": "Update or delete existing entry. Use entry_id from recent data or query_logs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "enum": ["meals", "symptoms", "vitals", "medications", "sleep", "exercise", "journal", "labs", "recipes"]
                },
                "entry_id": {"type": "integer", "description": "Entry ID"},
                "action": {
                    "type": "string", "enum": ["update", "delete"],
                    "description": "update to modify, delete to remove"
                },
                "updates": {
                    "type": "object",
                    "description": "Fields to update (action=update only). E.g. {'severity': 6, 'notes': 'worse now'}"
                }
            },
            "required": ["table", "entry_id", "action"]
        }
    },
    {
        "name": "get_profile",
        "description": "Get patient's full medical profile.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "update_profile",
        "description": "Update the user's medical profile. Use dot notation for nested fields (e.g., 'conditions.chronic', 'upcoming_appointments.elf_test'). Actions: 'append' (add to list), 'set' (replace value), 'remove' (remove from list), 'delete' (delete a dictionary key).",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "description": "Dot-notation path (e.g., 'lifestyle.notes', 'conditions.chronic', 'upcoming_appointments.elf_test')"
                },
                "action": {
                    "type": "string", "enum": ["append", "set", "remove", "delete"],
                    "description": "Action: append to list, set value, remove from list, or delete dict key"
                },
                "value": {
                    "type": "string",
                    "description": "Value to add, set, or remove (not used for 'delete')"
                }
            },
            "required": ["section", "action", "value"]
        }
    },
    {
        "name": "save_recipe",
        "description": "Save recipe with total nutrition & servings. Per-serving calc is automatic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "servings": {"type": "number", "description": "How many servings (default 1)"},
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit": {"type": "string"},
                            "calories": {"type": "number"},
                            "protein": {"type": "number", "description": "g"},
                            "carbs": {"type": "number", "description": "g"},
                            "fat": {"type": "number", "description": "g"},
                            "fiber": {"type": "number", "description": "g"},
                            "vitamin_b12": {"type": "number", "description": "μg"},
                            "vitamin_d": {"type": "number", "description": "IU"},
                            "folate": {"type": "number", "description": "μg"},
                            "iron": {"type": "number", "description": "mg"},
                            "zinc": {"type": "number", "description": "mg"},
                            "magnesium": {"type": "number", "description": "mg"},
                            "calcium": {"type": "number", "description": "mg"},
                            "potassium": {"type": "number", "description": "mg"},
                            "omega_3": {"type": "number", "description": "g"},
                            "vitamin_a": {"type": "number", "description": "IU"},
                            "vitamin_c": {"type": "number", "description": "mg"},
                        },
                        "required": ["name", "calories", "protein", "carbs", "fat"]
                    }
                },
                "notes": {"type": "string"}
            },
            "required": ["name", "ingredients"]
        }
    },
    {
        "name": "get_recipe",
        "description": "Get saved recipe by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "list_recipes",
        "description": "List all saved recipes with per-serving nutrition.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "delete_recipe",
        "description": "Delete saved recipe.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "get_nutrition_summary",
        "description": "Get nutrition totals & daily averages for time period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to summarize (default 3)"}
            }
        }
    },
    {
        "name": "get_nutrition_alerts",
        "description": "Check nutrient deficiencies (<70% RDA).",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Days to analyze (default 3)"}
            }
        }
    },
]
