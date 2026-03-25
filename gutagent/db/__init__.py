"""Database module - re-exports all functions for backward compatibility.

Structure:
- connection.py: DB setup, connection handling
- common.py: Shared utilities (round_nutrition, update_log, delete_log, get_logs_by_date)
- logs.py: ALL logging (meals, symptoms, vitals, labs, meds, sleep, exercise, journal)
- recipes.py: Recipe CRUD
- nutrition.py: RDA targets, summaries, alerts
"""

# Connection and setup
from .connection import (
    DB_PATH,
    get_connection,
    init_db,
    validate_timestamp,
)

# Common utilities
from .common import (
    update_log,
    delete_log,
    get_logs_by_date,
    round_nutrition,
)

# Logs (all health data logging)
from .logs import (
    # Meals
    log_meal_with_nutrition,
    get_recent_meals,
    search_meals_by_food,
    # Symptoms
    log_symptom,
    get_recent_symptoms,
    search_symptoms,
    # Medications
    log_medication_event,
    get_current_and_recent_meds,
    get_meds_summary,
    # Vitals
    log_vital,
    get_recent_vitals,
    get_vitals_summary,
    # Labs
    log_lab,
    get_labs_by_date,
    get_latest_labs_per_test,
    search_labs_by_test,
    # Sleep
    log_sleep,
    get_recent_sleep,
    # Exercise
    log_exercise,
    get_recent_exercise,
    # Journal
    log_journal_entry,
    get_recent_journal,
)

# Recipes
from .recipes import (
    save_recipe,
    get_recipe,
    list_recipes,
    delete_recipe,
)

# Nutrition
from .nutrition import (
    RDA_TARGETS,
    set_rda_targets,
    get_nutrition_summary,
    get_nutrition_alerts,
)

# Backward compatibility alias
_round_nutrition = round_nutrition
