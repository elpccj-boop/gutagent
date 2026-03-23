"""Comprehensive tests for GutAgent - all tools and functionality.

# Run all tests
pytest tests/test_gutagent.py -v

# Run specific test class
pytest tests/test_gutagent.py::TestMeals -v

# Run single test
pytest tests/test_gutagent.py::TestMeals::test_log_meal_with_nutrition -v

# Stop on first failure
pytest tests/test_gutagent.py -v -x

**When to run tests:**
- After editing db/ modules — run all tests
- After editing registry.py — run TestRegistry class
- After editing profile.py — run TestProfile class
"""

import pytest
import os
import json
import tempfile
from datetime import datetime

# =============================================================================
# IMPORTS - all db functions
# =============================================================================

from gutagent.db import (
    # Connection/setup
    init_db,
    # Meals
    log_meal_with_nutrition,
    get_recent_meals,
    search_meals_by_food,
    # Symptoms
    log_symptom,
    get_recent_symptoms,
    search_symptoms,
    # Vitals
    log_vital,
    get_recent_vitals,
    # Labs
    log_lab,
    get_recent_labs,
    get_latest_labs_per_test,
    # Medications
    log_medication_event,
    get_recent_meds,
    # Sleep
    log_sleep,
    get_recent_sleep,
    # Exercise
    log_exercise,
    get_recent_exercise,
    # Journal
    log_journal_entry,
    get_recent_journal,
    # Recipes
    save_recipe,
    get_recipe,
    list_recipes,
    delete_recipe,
    # Nutrition
    get_nutrition_summary,
    get_nutrition_alerts,
    set_rda_targets,
    RDA_TARGETS,
    # Common
    update_log,
    delete_log,
    get_logs_by_date,
    get_connection,
    round_nutrition,
)

# Private functions for RDA tests
from gutagent.db.nutrition import _calculate_rda_targets, _calculate_age_from_dob

# Profile
from gutagent.profile import load_profile, save_profile, update_profile

# Registry
from gutagent.tools.registry import execute_tool


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Use a temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    from pathlib import Path
    temp_path = Path(path)

    # Patch at the source (paths module) and where it's imported
    monkeypatch.setattr("gutagent.paths.DB_PATH", temp_path)
    monkeypatch.setattr("gutagent.db.connection.DB_PATH", temp_path)

    init_db()

    yield path

    os.unlink(path)


@pytest.fixture(autouse=True)
def temp_profile(monkeypatch, tmp_path):
    """Use a temporary profile for each test."""
    profile_path = tmp_path / "profile.json"

    test_profile = {
        "personal": {
            "sex": "female",
            "dob": "1971-03-20"
        }
    }

    profile_path.write_text(json.dumps(test_profile, indent=2))

    # Patch at the source (paths module) and where it's imported
    monkeypatch.setattr("gutagent.paths.PROFILE_PATH", profile_path)
    monkeypatch.setattr("gutagent.profile.PROFILE_PATH", profile_path)

    yield profile_path


# =============================================================================
# MEAL TESTS
# =============================================================================

class TestMeals:
    """Tests for meal logging."""

    def test_log_meal_with_nutrition(self):
        """Log a meal with full nutrition data."""
        result = log_meal_with_nutrition(
            meal_type="breakfast",
            description="scrambled eggs",
            items=[{"food_name": "eggs", "quantity": 2, "unit": "piece"}],
            nutrition={"calories": 140, "protein": 12, "fat": 10, "carbs": 1}
        )

        assert result["status"] == "logged"
        assert result["meal_type"] == "breakfast"
        assert "id" in result
        assert "140 cal" in result["summary"]

    def test_log_meal_with_timestamp(self):
        """Log a meal with specific timestamp."""
        result = log_meal_with_nutrition(
            meal_type="dinner",
            description="late dinner",
            items=[],
            nutrition={"calories": 500},
            occurred_at="2026-03-15 21:00:00"
        )

        assert "2026-03-15" in result["when"]

    def test_get_recent_meals(self):
        """Retrieve recent meals."""
        log_meal_with_nutrition(
            meal_type="lunch",
            description="test meal",
            items=[],
            nutrition={"calories": 300}
        )

        meals = get_recent_meals(days_back=1)
        assert len(meals) == 1
        assert meals[0]["description"] == "test meal"

    def test_search_meals_by_food(self):
        """Search meals by food term."""
        log_meal_with_nutrition(
            meal_type="lunch",
            description="chicken curry with rice",
            items=[],
            nutrition={"calories": 400}
        )
        log_meal_with_nutrition(
            meal_type="dinner",
            description="fish tacos",
            items=[],
            nutrition={"calories": 350}
        )

        results = search_meals_by_food("chicken")
        assert len(results) == 1
        assert "chicken" in results[0]["description"]


# =============================================================================
# SYMPTOM TESTS
# =============================================================================

class TestSymptoms:
    """Tests for symptom logging."""

    def test_log_symptom(self):
        """Log a symptom."""
        result = log_symptom(
            symptom="headache",
            severity=6,
            timing="after lunch",
            notes="mild throbbing"
        )

        assert result["status"] == "logged"
        assert result["symptom"] == "headache"
        assert result["severity"] == 6

    def test_get_recent_symptoms(self):
        """Retrieve recent symptoms."""
        log_symptom(symptom="nausea", severity=4)
        log_symptom(symptom="fatigue", severity=5)

        symptoms = get_recent_symptoms(days_back=1)
        assert len(symptoms) == 2

    def test_search_symptoms(self):
        """Search symptoms by term."""
        log_symptom(symptom="stomach pain", severity=5)
        log_symptom(symptom="headache", severity=3)

        results = search_symptoms("stomach")
        assert len(results) == 1
        assert "stomach" in results[0]["symptom"]


# =============================================================================
# VITALS TESTS
# =============================================================================

class TestVitals:
    """Tests for vitals logging."""

    def test_log_blood_pressure(self):
        """Log blood pressure reading."""
        result = log_vital(
            vital_type="blood_pressure",
            systolic=120,
            diastolic=80,
            heart_rate=72
        )

        assert result["status"] == "logged"
        assert "120/80" in result["reading"]

    def test_log_weight(self):
        """Log weight reading."""
        result = log_vital(
            vital_type="weight",
            value=70.5,
            unit="kg"
        )

        assert result["status"] == "logged"

    def test_log_temperature(self):
        """Log temperature reading."""
        result = log_vital(
            vital_type="temperature",
            value=98.6,
            unit="F"
        )

        assert result["status"] == "logged"

    def test_get_recent_vitals(self):
        """Retrieve recent vitals."""
        log_vital(vital_type="blood_pressure", systolic=118, diastolic=78, heart_rate=70)
        log_vital(vital_type="blood_pressure", systolic=122, diastolic=82, heart_rate=75)

        result = get_recent_vitals(days_back=1, vital_type="blood_pressure")
        assert isinstance(result, (str, dict))


# =============================================================================
# LAB TESTS
# =============================================================================

class TestLabs:
    """Tests for lab result logging."""

    def test_log_lab_minimal(self):
        """Log lab with minimal info."""
        result = log_lab(test_name="CRP")

        assert result["status"] == "logged"
        assert result["test_name"] == "CRP"

    def test_log_lab_complete(self):
        """Log lab with all fields."""
        result = log_lab(
            test_name="Hemoglobin",
            test_date="2026-03-15",
            value=14.2,
            unit="g/dL",
            reference_range="12.0-16.0",
            status="normal",
            notes="routine checkup"
        )

        assert result["status"] == "logged"
        assert result["test_date"] == "2026-03-15"
        assert "14.2" in result["summary"]

    def test_log_lab_infers_date(self):
        """Log lab without date uses today."""
        result = log_lab(test_name="WBC", value=7.5)

        today = datetime.now().strftime("%Y-%m-%d")
        assert result["test_date"] == today

    def test_get_recent_labs(self):
        """Get labs from most recent date."""
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-10", value=10)
        log_lab(test_name="WBC", test_date="2026-03-15", value=7.0)

        labs = get_recent_labs()
        assert len(labs) == 1
        assert labs[0]["test_name"] == "WBC"

    def test_get_recent_labs_by_test_name(self):
        """Get labs filtered by date."""
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-10", value=10)

        labs = get_recent_labs(test_date="2026-03-10")
        assert len(labs) == 2

    def test_get_latest_labs_per_test(self):
        """Get most recent value for each test type."""
        log_lab(test_name="CRP", test_date="2026-03-01", value=0.3)
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-05", value=12)

        labs = get_latest_labs_per_test()
        assert len(labs) == 2

        crp = next(l for l in labs if l["test_name"] == "CRP")
        assert crp["value"] == 0.5

    def test_get_logs_by_date_labs(self):
        """Get labs by specific date."""
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-10", value=10)
        log_lab(test_name="WBC", test_date="2026-03-15", value=7.0)

        labs = get_logs_by_date("labs", "2026-03-10")
        assert len(labs) == 2

    def test_update_lab(self):
        """Update a lab result."""
        result = log_lab(test_name="CRP", value=0.5, status="normal")
        lab_id = result["id"]

        update_result = update_log("labs", lab_id, {"status": "abnormal", "value": 2.5})
        assert update_result["status"] == "updated"

        conn = get_connection()
        row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
        conn.close()

        assert row["status"] == "abnormal"
        assert row["value"] == 2.5

    def test_delete_lab(self):
        """Delete a lab result."""
        result = log_lab(test_name="CRP", value=0.5)
        lab_id = result["id"]

        delete_result = delete_log("labs", lab_id)
        assert delete_result["status"] == "deleted"

        conn = get_connection()
        row = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
        conn.close()

        assert row is None


# =============================================================================
# MEDICATION TESTS
# =============================================================================

class TestMedications:
    """Tests for medication logging."""

    def test_log_medication_taken(self):
        """Log taking a medication."""
        result = log_medication_event(
            medication="Ibuprofen",
            event_type="taken",
            dose="400mg"
        )

        assert result["status"] == "logged"
        assert result["medication"] == "Ibuprofen"

    def test_log_medication_started(self):
        """Log starting a new medication."""
        result = log_medication_event(
            medication="Prednisone",
            event_type="started",
            dose="20mg daily",
            notes="for flare"
        )

        assert result["status"] == "logged"
        assert result["event"] == "started"

    def test_get_recent_meds(self):
        """Retrieve recent medication events."""
        log_medication_event(medication="Med1", event_type="taken")
        log_medication_event(medication="Med2", event_type="started")

        meds = get_recent_meds(days_back=1)
        assert len(meds) == 2


# =============================================================================
# SLEEP TESTS
# =============================================================================

class TestSleep:
    """Tests for sleep logging."""

    def test_log_sleep(self):
        """Log sleep entry."""
        result = log_sleep(
            hours=7.5,
            quality="good",
            notes="woke once"
        )

        assert result["status"] == "logged"
        assert result["hours"] == 7.5

    def test_get_recent_sleep(self):
        """Retrieve recent sleep entries."""
        log_sleep(hours=7, quality="good")
        log_sleep(hours=6, quality="poor")

        sleep = get_recent_sleep(days_back=1)
        assert len(sleep) == 2


# =============================================================================
# EXERCISE TESTS
# =============================================================================

class TestExercise:
    """Tests for exercise logging."""

    def test_log_exercise(self):
        """Log exercise entry."""
        result = log_exercise(
            activity="walking",
            duration_minutes=30,
            notes="morning walk"
        )

        assert result["status"] == "logged"
        assert result["activity"] == "walking"

    def test_get_recent_exercise(self):
        """Retrieve recent exercise entries."""
        log_exercise(activity="walking", duration_minutes=30)
        log_exercise(activity="yoga", duration_minutes=45)

        exercise = get_recent_exercise(days_back=1)
        assert len(exercise) == 2


# =============================================================================
# JOURNAL TESTS
# =============================================================================

class TestJournal:
    """Tests for journal logging."""

    def test_log_journal(self):
        """Log journal entry."""
        result = log_journal_entry(description="Feeling better today")

        assert result["status"] == "logged"
        assert "better" in result["description"]

    def test_get_recent_journal(self):
        """Retrieve recent journal entries."""
        log_journal_entry(description="Entry 1")
        log_journal_entry(description="Entry 2")

        journal = get_recent_journal(days_back=1)
        assert len(journal) == 2


# =============================================================================
# RECIPE TESTS
# =============================================================================

class TestRecipes:
    """Tests for recipe management."""

    def test_save_recipe(self):
        """Save a new recipe."""
        result = save_recipe(
            name="Simple Oatmeal",
            ingredients=[
                {"name": "oats", "quantity": 1, "unit": "cup", "calories": 300}
            ],
            notes="Add honey to taste",
            servings=2
        )

        assert result["status"] == "created"
        assert result["name"] == "Simple Oatmeal"

    def test_get_recipe(self):
        """Retrieve a saved recipe."""
        save_recipe(
            name="Test Recipe",
            ingredients=[{"name": "item", "calories": 100}],
            servings=1
        )

        recipe = get_recipe("Test Recipe")
        assert recipe is not None
        assert recipe["name"] == "Test Recipe"

    def test_get_recipe_case_insensitive(self):
        """Recipe lookup is case-insensitive."""
        save_recipe(name="My Recipe", ingredients=[], servings=1)

        recipe = get_recipe("MY RECIPE")
        assert recipe is not None

    def test_list_recipes(self):
        """List all recipes."""
        save_recipe(name="Recipe A", ingredients=[], servings=1)
        save_recipe(name="Recipe B", ingredients=[], servings=1)

        recipes = list_recipes()
        assert len(recipes) == 2

    def test_delete_recipe(self):
        """Delete a recipe."""
        save_recipe(name="To Delete", ingredients=[], servings=1)

        result = delete_recipe("To Delete")
        assert result["status"] == "deleted"

        recipe = get_recipe("To Delete")
        assert recipe is None

    def test_update_recipe(self):
        """Updating existing recipe."""
        save_recipe(name="Update Me", ingredients=[{"name": "old"}], servings=1)
        save_recipe(name="Update Me", ingredients=[{"name": "new"}], servings=2)

        recipe = get_recipe("Update Me")
        assert recipe["servings"] == 2
        assert recipe["ingredients"][0]["name"] == "new"


# =============================================================================
# NUTRITION TESTS
# =============================================================================

class TestNutrition:
    """Tests for nutrition tracking."""

    def test_nutrition_summary_empty(self):
        """Nutrition summary with no data."""
        result = get_nutrition_summary(days=3)
        assert "No nutrition data" in result

    def test_nutrition_summary_with_data(self):
        """Nutrition summary with meal data."""
        log_meal_with_nutrition(
            meal_type="lunch",
            description="test",
            items=[],
            nutrition={"calories": 500, "protein": 30, "carbs": 50, "fat": 20}
        )

        result = get_nutrition_summary(days=1)
        assert "500" in result or "cal" in result.lower()

    def test_nutrition_alerts_empty(self):
        """Nutrition alerts with no data."""
        result = get_nutrition_alerts(days=3)
        assert "No nutrition data" in result

    def test_nutrition_alerts_deficiency(self):
        """Nutrition alerts detect deficiencies."""
        set_rda_targets({"personal": {"sex": "female", "dob": "1990-01-01"}})

        log_meal_with_nutrition(
            meal_type="lunch",
            description="low iron meal",
            items=[],
            nutrition={"calories": 500, "iron": 1}
        )

        result = get_nutrition_alerts(days=1)
        assert "iron" in result.lower() or "ALERTS" in result

    def test_nutrition_rounding(self):
        """Nutrition values are rounded appropriately."""
        result = round_nutrition({
            "calories": 123.456,
            "protein": 12.789,
            "vitamin_b12": 2.456,
            "iron": 8.234
        })

        assert result["calories"] == 123
        assert result["protein"] == 13
        assert result["vitamin_b12"] == 2.5
        assert result["iron"] == 8.2


# =============================================================================
# CORRECTION TESTS
# =============================================================================

class TestCorrections:
    """Tests for updating/deleting logs."""

    def test_update_meal(self):
        """Update a meal entry."""
        result = log_meal_with_nutrition(
            meal_type="lunch",
            description="original",
            items=[],
            nutrition={"calories": 300}
        )
        meal_id = result["id"]

        update_result = update_log("meals", meal_id, {"description": "updated"})
        assert update_result["status"] == "updated"

    def test_delete_meal(self):
        """Delete a meal entry."""
        result = log_meal_with_nutrition(
            meal_type="lunch",
            description="to delete",
            items=[],
            nutrition={"calories": 300}
        )
        meal_id = result["id"]

        delete_result = delete_log("meals", meal_id)
        assert delete_result["status"] == "deleted"

    def test_update_symptom(self):
        """Update a symptom entry."""
        result = log_symptom(symptom="headache", severity=5)
        symptom_id = result["id"]

        update_result = update_log("symptoms", symptom_id, {"severity": 7})
        assert update_result["status"] == "updated"

    def test_delete_symptom(self):
        """Delete a symptom entry."""
        result = log_symptom(symptom="to delete", severity=3)
        symptom_id = result["id"]

        delete_result = delete_log("symptoms", symptom_id)
        assert delete_result["status"] == "deleted"


# =============================================================================
# DATE SEARCH TESTS
# =============================================================================

class TestDateSearch:
    """Tests for date-based log queries."""

    def test_get_logs_by_date_meals(self):
        """Get meals by specific date."""
        log_meal_with_nutrition(
            meal_type="lunch",
            description="today's meal",
            items=[],
            nutrition={"calories": 400},
            occurred_at="2026-03-15 12:00:00"
        )

        meals = get_logs_by_date("meals", "2026-03-15")
        assert len(meals) == 1

    def test_get_logs_by_date_symptoms(self):
        """Get symptoms by specific date."""
        log_symptom(
            symptom="test",
            severity=5,
            occurred_at="2026-03-15 10:00:00"
        )

        symptoms = get_logs_by_date("symptoms", "2026-03-15")
        assert len(symptoms) == 1


# =============================================================================
# REGISTRY TESTS
# =============================================================================

class TestRegistry:
    """Tests for tool execution via registry."""

    def test_execute_log_meal(self):
        """Execute log_meal tool."""
        result = execute_tool("log_meal", {
            "meal_type": "breakfast",
            "description": "eggs and toast",
            "items": [
                {"food_name": "eggs", "quantity": 2, "unit": "piece",
                 "calories": 140, "protein": 12, "fat": 10, "carbs": 1}
            ]
        })

        assert "logged" in result.lower()

    def test_execute_log_meal_with_recipe(self):
        """Execute log_meal with recipe reference."""
        save_recipe(
            name="Morning Oats",
            ingredients=[{"name": "oats", "calories": 300, "protein": 10}],
            servings=1
        )

        result = execute_tool("log_meal", {
            "meal_type": "breakfast",
            "description": "Morning Oats",
            "items": [{"recipe": "Morning Oats", "servings": 1}]
        })

        assert "logged" in result.lower()

    def test_execute_log_symptom(self):
        """Execute log_symptom tool."""
        result = execute_tool("log_symptom", {
            "symptom": "nausea",
            "severity": 4,
            "timing": "after eating"
        })

        assert "logged" in result.lower()

    def test_execute_log_vital(self):
        """Execute log_vital tool."""
        result = execute_tool("log_vital", {
            "vital_type": "blood_pressure",
            "systolic": 118,
            "diastolic": 76,
            "heart_rate": 68
        })

        assert "logged" in result.lower()

    def test_execute_query_logs_recent_meals(self):
        """Execute query_logs for recent meals."""
        log_meal_with_nutrition(
            meal_type="lunch",
            description="test",
            items=[],
            nutrition={"calories": 300}
        )

        result = execute_tool("query_logs", {
            "query_type": "recent_meals",
            "days_back": 1
        })

        assert "test" in result.lower()

    def test_execute_query_logs_date_search(self):
        """Execute query_logs with date filter."""
        log_meal_with_nutrition(
            meal_type="lunch",
            description="dated meal",
            items=[],
            nutrition={"calories": 300},
            occurred_at="2026-03-15 12:00:00"
        )

        result = execute_tool("query_logs", {
            "query_type": "date_search",
            "table": "meals",
            "date": "2026-03-15"
        })

        assert "dated meal" in result.lower()

    def test_execute_correct_log_update(self):
        """Execute correct_log to update."""
        meal = log_meal_with_nutrition(
            meal_type="lunch",
            description="original",
            items=[],
            nutrition={"calories": 300}
        )

        result = execute_tool("correct_log", {
            "table": "meals",
            "entry_id": meal["id"],
            "action": "update",
            "updates": {"description": "corrected"}
        })

        assert "updated" in result.lower()

    def test_execute_correct_log_delete(self):
        """Execute correct_log to delete."""
        meal = log_meal_with_nutrition(
            meal_type="lunch",
            description="to delete",
            items=[],
            nutrition={"calories": 300}
        )

        result = execute_tool("correct_log", {
            "table": "meals",
            "entry_id": meal["id"],
            "action": "delete"
        })

        assert "deleted" in result.lower()

    def test_execute_save_recipe(self):
        """Execute save_recipe tool."""
        result = execute_tool("save_recipe", {
            "name": "Test Recipe",
            "ingredients": [{"name": "item", "calories": 100}],
            "servings": 2
        })

        assert "created" in result.lower() or "Test Recipe" in result

    def test_execute_get_recipe(self):
        """Execute get_recipe tool."""
        save_recipe(name="Lookup Recipe", ingredients=[], servings=1)

        result = execute_tool("get_recipe", {"name": "Lookup Recipe"})

        assert "Lookup Recipe" in result

    def test_execute_list_recipes(self):
        """Execute list_recipes tool."""
        save_recipe(name="Recipe 1", ingredients=[], servings=1)
        save_recipe(name="Recipe 2", ingredients=[], servings=1)

        result = execute_tool("list_recipes", {})

        assert "Recipe 1" in result or "Recipe 2" in result

    def test_execute_unknown_tool(self):
        """Unknown tool returns error."""
        result = execute_tool("nonexistent_tool", {})

        assert "unknown" in result.lower() or "error" in result.lower()

    def test_execute_get_nutrition_summary(self):
        """Execute get_nutrition_summary tool."""
        result = execute_tool("get_nutrition_summary", {"days": 3})

        assert "nutrition" in result.lower() or "no" in result.lower()

    def test_execute_get_nutrition_alerts(self):
        """Execute get_nutrition_alerts tool."""
        result = execute_tool("get_nutrition_alerts", {"days": 3})

        assert "nutrition" in result.lower() or "no" in result.lower()

    def test_execute_log_lab(self):
        """Execute log_lab tool."""
        result = execute_tool("log_lab", {
            "test_name": "CRP",
            "test_date": "2026-03-15",
            "value": 0.5,
            "unit": "mg/L",
            "reference_range": "0-3",
            "status": "normal"
        })

        assert "logged" in result.lower()

    def test_execute_log_lab_minimal(self):
        """Execute log_lab with minimal info."""
        result = execute_tool("log_lab", {"test_name": "ESR"})

        assert "logged" in result.lower()

    def test_execute_query_logs_date_search_labs(self):
        """Execute query_logs for labs by date."""
        log_lab(test_name="CRP", test_date="2026-03-15", value=0.5)

        result = execute_tool("query_logs", {
            "query_type": "date_search",
            "table": "labs",
            "date": "2026-03-15"
        })

        assert "crp" in result.lower()

    def test_execute_correct_log_labs(self):
        """Execute correct_log for labs."""
        lab = log_lab(test_name="CRP", value=0.5, status="normal")

        result = execute_tool("correct_log", {
            "table": "labs",
            "entry_id": lab["id"],
            "action": "update",
            "updates": {"status": "abnormal"}
        })

        assert "updated" in result.lower()

    def test_execute_correct_log_delete_lab(self):
        """Execute correct_log to delete lab."""
        lab = log_lab(test_name="ToDelete", value=1.0)

        result = execute_tool("correct_log", {
            "table": "labs",
            "entry_id": lab["id"],
            "action": "delete"
        })

        assert "deleted" in result.lower()


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_meal_items(self):
        """Log meal with no items."""
        result = log_meal_with_nutrition(
            meal_type="snack",
            description="quick bite",
            items=[],
            nutrition={"calories": 100}
        )

        assert result["status"] == "logged"

    def test_recipe_not_found(self):
        """Get non-existent recipe."""
        recipe = get_recipe("Does Not Exist")
        assert recipe is None

    def test_delete_nonexistent(self):
        """Delete non-existent entry."""
        result = delete_log("meals", 99999)
        assert result["status"] == "deleted"

    def test_timestamp_parsing(self):
        """Various timestamp formats."""
        result = log_symptom(
            symptom="test",
            severity=3,
            occurred_at="2026-03-15T14:30:00"
        )
        assert result["status"] == "logged"

    def test_special_characters_in_description(self):
        """Handle special characters."""
        result = log_meal_with_nutrition(
            meal_type="lunch",
            description="Bob's café — 'special' meal & more",
            items=[],
            nutrition={"calories": 400}
        )

        assert result["status"] == "logged"
        meals = get_recent_meals(days_back=1)
        assert "Bob's" in meals[0]["description"]


# =============================================================================
# PROFILE TESTS
# =============================================================================

class TestProfile:
    """Tests for profile management."""

    def test_load_profile_not_found(self, monkeypatch):
        """Load profile when file doesn't exist."""
        from pathlib import Path
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)

        monkeypatch.setattr("gutagent.profile.PROFILE_PATH", Path(path))

        result = load_profile()
        assert "error" in result

    def test_save_and_load_profile(self):
        """Save and load a profile."""
        profile = {
            "name": "Test User",
            "conditions": {"chronic": ["condition1"]}
        }
        save_profile(profile)

        loaded = load_profile()
        assert loaded["name"] == "Test User"
        assert "condition1" in loaded["conditions"]["chronic"]

    def test_update_profile_set(self):
        """Update profile with set action."""
        save_profile({"name": "Old Name"})

        result = update_profile("name", "set", "New Name")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert loaded["name"] == "New Name"

    def test_update_profile_append(self):
        """Update profile with append action."""
        save_profile({"conditions": {"chronic": ["existing"]}})

        result = update_profile("conditions.chronic", "append", "new condition")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert "new condition" in loaded["conditions"]["chronic"]
        assert "existing" in loaded["conditions"]["chronic"]

    def test_update_profile_append_creates_list(self):
        """Append to non-existent key creates list."""
        save_profile({})

        result = update_profile("conditions.chronic", "append", "first item")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert loaded["conditions"]["chronic"] == ["first item"]

    def test_update_profile_remove(self):
        """Update profile with remove action."""
        save_profile({"meds": ["aspirin daily", "vitamin D"]})

        result = update_profile("meds", "remove", "aspirin")
        assert result["status"] == "removed"
        assert result["items_removed"] == 1

        loaded = load_profile()
        assert len(loaded["meds"]) == 1
        assert "vitamin D" in loaded["meds"]

    def test_update_profile_remove_not_found(self):
        """Remove non-existent item returns error."""
        save_profile({"meds": ["aspirin"]})

        result = update_profile("meds", "remove", "nonexistent")
        assert "error" in result

    def test_update_profile_append_to_non_list(self):
        """Append to non-list returns error."""
        save_profile({"name": "Test"})

        result = update_profile("name", "append", "extra")
        assert "error" in result

    def test_update_profile_unknown_action(self):
        """Unknown action returns error."""
        save_profile({})

        result = update_profile("key", "invalid_action", "value")
        assert "error" in result

    def test_update_profile_nested_path(self):
        """Update deeply nested path."""
        save_profile({"level1": {"level2": {"level3": "old"}}})

        result = update_profile("level1.level2.level3", "set", "new")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert loaded["level1"]["level2"]["level3"] == "new"

    def test_update_profile_delete(self):
        """Test deleting a dictionary key from profile."""
        profile = {
            "upcoming_appointments": {
                "elf_test": "March 2026",
                "gastro": "April 2026"
            }
        }
        save_profile(profile)

        result = update_profile(
            section="upcoming_appointments.elf_test",
            action="delete",
            value=""
        )

        assert result['status'] == 'deleted'

        updated = load_profile()
        assert 'elf_test' not in updated['upcoming_appointments']
        assert 'gastro' in updated['upcoming_appointments']


# =============================================================================
# RDA TESTS
# =============================================================================

class TestRDA:
    """Tests for RDA calculations."""

    def test_rda_calculation_female_55(self):
        """Test RDA targets for 55-year-old female."""
        targets = _calculate_rda_targets('female', 55)

        assert targets['iron']['target'] == 8  # Postmenopausal
        assert targets['calcium']['target'] == 1200  # Age 51+
        assert targets['fiber']['target'] == 21  # Female 51+
        assert targets['vitamin_a']['target'] == 2333  # Female
        assert targets['vitamin_a']['unit'] == 'IU'
        assert targets['vitamin_c']['target'] == 75  # Female

    def test_rda_calculation_male_30(self):
        """Test RDA targets for 30-year-old male."""
        targets = _calculate_rda_targets('male', 30)

        assert targets['iron']['target'] == 8
        assert targets['calcium']['target'] == 1000  # Under 71
        assert targets['fiber']['target'] == 38  # Male under 51
        assert targets['vitamin_a']['target'] == 3000  # Male (IU)
        assert targets['vitamin_c']['target'] == 90  # Male

    def test_calculate_age_from_dob(self):
        """Test age calculation from date of birth."""
        today = datetime.now()

        dob_55_years = today.replace(year=today.year - 55).strftime("%Y-%m-%d")
        assert _calculate_age_from_dob(dob_55_years) == 55

        dob_30_years = today.replace(year=today.year - 30).strftime("%Y-%m-%d")
        assert _calculate_age_from_dob(dob_30_years) == 30

        assert _calculate_age_from_dob("YYYY-MM-DD") is None
        assert _calculate_age_from_dob("") is None
        assert _calculate_age_from_dob(None) is None

    def test_init_models_with_profile(self):
        """Test that set_rda_targets sets RDA_TARGETS from profile."""
        profile = {
            "personal": {
                "sex": "female",
                "dob": "1971-03-20"
            }
        }

        set_rda_targets(profile)

        assert RDA_TARGETS['calcium']['target'] == 1200
        assert RDA_TARGETS['iron']['target'] == 8

    def test_save_profile_refreshes_rda(self):
        """Test that saving profile refreshes RDA targets."""
        profile = {
            "personal": {
                "sex": "female",
                "dob": "1971-03-20"
            }
        }

        save_profile(profile)

        assert RDA_TARGETS['calcium']['target'] == 1200
        assert RDA_TARGETS['iron']['target'] == 8


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
