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
# IMPORTS
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
    get_vitals_summary,
    # Labs
    log_lab,
    get_labs_by_date,
    get_latest_labs_per_test,
    search_labs_by_test,
    # Medications
    log_medication_event,
    get_current_and_recent_meds,
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

# Agent and LLM
from gutagent.agent import run_agent
from gutagent.llm.base import LLMResponse
from gutagent.llm import get_provider
from gutagent.core import format_recent_logs

# System prompts
from gutagent.prompts.system import (
    get_patient_data,
    build_patient_data_context,
    build_turn_context,
    build_static_system_prompt,
)


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
        """Retrieve recent vitals as list."""
        log_vital(vital_type="blood_pressure", systolic=118, diastolic=78, heart_rate=70)
        log_vital(vital_type="blood_pressure", systolic=122, diastolic=82, heart_rate=75)

        result = get_recent_vitals(days_back=1, vital_type="blood_pressure")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_get_vitals_summary(self):
        """Retrieve vitals as formatted summary."""
        log_vital(vital_type="blood_pressure", systolic=118, diastolic=78, heart_rate=70)

        result = get_vitals_summary(days_back=1, vital_type="blood_pressure")
        assert isinstance(result, str)
        assert "118" in result


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

    def test_get_labs_by_date(self):
        """Get labs from most recent date."""
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-10", value=10)
        log_lab(test_name="WBC", test_date="2026-03-15", value=7.0)

        labs = get_labs_by_date()
        assert len(labs) == 1
        assert labs[0]["test_name"] == "WBC"

    def test_get_labs_by_date_specific(self):
        """Get labs filtered by date."""
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-10", value=10)
        log_lab(test_name="WBC", test_date="2026-03-15", value=10)

        labs = get_labs_by_date(test_date="2026-03-10")
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

    def test_search_labs_by_test(self):
        """Search for all results of a specific test."""
        log_lab(test_name="CRP", test_date="2026-03-01", value=0.3)
        log_lab(test_name="CRP", test_date="2026-03-10", value=0.5)
        log_lab(test_name="ESR", test_date="2026-03-05", value=12)

        labs = search_labs_by_test("CRP")
        assert len(labs) == 2
        assert all(l["test_name"] == "CRP" for l in labs)

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

    def test_get_current_and_recent_meds(self):
        """Retrieve current medications and recent changes."""
        log_medication_event(medication="Med1", event_type="taken")
        log_medication_event(medication="Med2", event_type="started")

        meds = get_current_and_recent_meds(days_back=1)
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
# AGENT INTEGRATION TESTS
# =============================================================================

from unittest.mock import MagicMock, patch

class TestAgent:
    """Integration tests for the agent loop."""

    def test_agent_simple_text_response(self):
        """Agent returns text when LLM gives end_turn."""

        # Mock LLM that returns a simple text response
        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Hello! How can I help you today?"}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 20}
        )

        mock_provider = MagicMock()
        mock_provider.chat.return_value = mock_response

        with patch('gutagent.agent.get_provider', return_value=mock_provider):
            profile = {"personal": {"sex": "female", "dob": "1990-01-01"}}
            response_text, recent_logs, last_exchange = run_agent(
                "Hello",
                profile=profile,
            )

        assert response_text == "Hello! How can I help you today?"
        assert recent_logs == {}
        assert last_exchange["user"] == "Hello"
        assert "Hello!" in last_exchange["assistant"]

    def test_agent_tool_call_and_response(self):
        """Agent executes tool and returns final response."""

        # First response: LLM wants to call a tool
        tool_call_response = LLMResponse(
            content=[{
                "type": "tool_use",
                "id": "tool_1",
                "name": "log_symptom",
                "input": {"symptom": "headache", "severity": 5}
            }],
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 50}
        )

        # Second response: LLM gives final text
        final_response = LLMResponse(
            content=[{"type": "text", "text": "I've logged your headache (severity 5)."}],
            stop_reason="end_turn",
            usage={"input_tokens": 150, "output_tokens": 30}
        )

        mock_provider = MagicMock()
        mock_provider.chat.side_effect = [tool_call_response, final_response]

        with patch('gutagent.agent.get_provider', return_value=mock_provider):
            profile = {"personal": {"sex": "female", "dob": "1990-01-01"}}
            response_text, recent_logs, last_exchange = run_agent(
                "I have a headache, about a 5",
                profile=profile,
            )

        assert "logged" in response_text.lower() or "headache" in response_text.lower()
        assert "symptoms" in recent_logs
        assert len(recent_logs["symptoms"]) == 1
        assert recent_logs["symptoms"][0]["symptom"] == "headache"

    def test_agent_tracks_meal_in_recent_logs(self):
        """Agent tracks logged meals in recent_logs for corrections."""

        # First response: log meal
        tool_call_response = LLMResponse(
            content=[{
                "type": "tool_use",
                "id": "tool_1",
                "name": "log_meal",
                "input": {
                    "meal_type": "breakfast",
                    "description": "eggs and toast",
                    "items": [
                        {"name": "eggs", "quantity": 2, "calories": 140, "protein": 12},
                        {"name": "toast", "quantity": 1, "calories": 80, "carbs": 15}
                    ]
                }
            }],
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 80}
        )

        final_response = LLMResponse(
            content=[{"type": "text", "text": "Logged your breakfast!"}],
            stop_reason="end_turn",
            usage={"input_tokens": 200, "output_tokens": 20}
        )

        mock_provider = MagicMock()
        mock_provider.chat.side_effect = [tool_call_response, final_response]

        with patch('gutagent.agent.get_provider', return_value=mock_provider):
            profile = {"personal": {"sex": "female", "dob": "1990-01-01"}}
            response_text, recent_logs, last_exchange = run_agent(
                "Had eggs and toast for breakfast",
                profile=profile,
            )

        assert "meals" in recent_logs
        assert len(recent_logs["meals"]) == 1
        assert recent_logs["meals"][0]["meal_type"] == "breakfast"

    def test_agent_preserves_last_exchange(self):
        """Agent includes last_exchange in messages for context."""

        mock_response = LLMResponse(
            content=[{"type": "text", "text": "Yes, I can help with that."}],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 20}
        )

        mock_provider = MagicMock()
        mock_provider.chat.return_value = mock_response

        with patch('gutagent.agent.get_provider', return_value=mock_provider):
            profile = {"personal": {"sex": "female", "dob": "1990-01-01"}}
            last_exchange = {
                "user": "Can you help me track meals?",
                "assistant": "Of course! What did you eat?"
            }

            response_text, recent_logs, new_exchange = run_agent(
                "yes",
                profile=profile,
                last_exchange=last_exchange,
            )

        # Check that chat was called with messages including last_exchange
        call_args = mock_provider.chat.call_args
        messages = call_args.kwargs.get('messages') or call_args[0][0]

        assert len(messages) == 3  # last_user, last_assistant, current_user
        assert messages[0]["content"] == "Can you help me track meals?"
        assert messages[1]["content"] == "Of course! What did you eat?"
        assert messages[2]["content"] == "yes"

    def test_agent_max_iterations_safety(self):
        """Agent stops after max iterations to prevent infinite loops."""

        # LLM keeps requesting tools forever
        endless_tool_response = LLMResponse(
            content=[{
                "type": "tool_use",
                "id": "tool_1",
                "name": "get_profile",
                "input": {}
            }],
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 20}
        )

        mock_provider = MagicMock()
        mock_provider.chat.return_value = endless_tool_response

        with patch('gutagent.agent.get_provider', return_value=mock_provider):
            profile = {"personal": {"sex": "female", "dob": "1990-01-01"}}
            response_text, recent_logs, last_exchange = run_agent(
                "Test infinite loop protection",
                profile=profile,
            )

        assert "maximum iterations" in response_text.lower()
        # Should have been called 10 times (max_iterations)
        assert mock_provider.chat.call_count == 10

    def test_agent_multiple_tool_calls(self):
        """Agent handles multiple tool calls in one response."""

        # LLM wants to call two tools at once
        multi_tool_response = LLMResponse(
            content=[
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "log_symptom",
                    "input": {"symptom": "fatigue", "severity": 6}
                },
                {
                    "type": "tool_use",
                    "id": "tool_2",
                    "name": "log_symptom",
                    "input": {"symptom": "headache", "severity": 4}
                }
            ],
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 80}
        )

        final_response = LLMResponse(
            content=[{"type": "text", "text": "Logged both symptoms."}],
            stop_reason="end_turn",
            usage={"input_tokens": 200, "output_tokens": 20}
        )

        mock_provider = MagicMock()
        mock_provider.chat.side_effect = [multi_tool_response, final_response]

        with patch('gutagent.agent.get_provider', return_value=mock_provider):
            profile = {"personal": {"sex": "female", "dob": "1990-01-01"}}
            response_text, recent_logs, last_exchange = run_agent(
                "Feeling fatigued (6) and have a headache (4)",
                profile=profile,
            )

        assert "symptoms" in recent_logs
        assert len(recent_logs["symptoms"]) == 2

    def test_format_recent_logs(self):
        """Test recent_logs formatting for prompt."""

        recent_logs = {
            "meals": [{"id": 1, "summary": "eggs and toast"}],
            "symptoms": [{"id": 2, "symptom": "headache", "severity": 5}]
        }

        result = format_recent_logs(recent_logs)

        assert "Recently logged" in result
        assert "meals" in result
        assert "id:1" in result
        assert "eggs and toast" in result
        assert "symptoms" in result
        assert "headache" in result

    def test_format_recent_logs_empty(self):
        """Test empty recent_logs returns empty string."""

        assert format_recent_logs({}) == ""
        assert format_recent_logs(None) == ""

    def test_format_recent_logs_recipe(self):
        """Test recipe formatting shows name and ingredients."""

        recent_logs = {
            "recipes": [{
                "id": 5,
                "name": "Masala Tea",
                "ingredients": [
                    {"name": "tea", "quantity": 2, "unit": "tsp"},
                    {"name": "milk", "quantity": 1, "unit": "cup"},
                    {"name": "sugar", "quantity": 1, "unit": "tbsp"},
                ]
            }]
        }

        result = format_recent_logs(recent_logs)

        assert "recipes" in result
        assert "id:5" in result
        assert "Masala Tea" in result
        assert "tea" in result
        assert "milk" in result


# =============================================================================
# API ENDPOINT TESTS
# =============================================================================

# TODO: API tests need proper test environment setup
# Currently server.py loads DB/profile at module import time,
# so these tests would use real data instead of test fixtures.
# Need to refactor server.py to accept injected dependencies,
# or create a separate test server configuration.

# Skip API tests if FastAPI not installed
try:
    from fastapi.testclient import TestClient
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

@pytest.mark.skip(reason="API tests need test environment setup - uses real DB/profile")
@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
class TestAPI:
    """Tests for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for API with auth."""
        import os
        import base64
        from fastapi.testclient import TestClient
        from gutagent.api.server import app

        # Get auth credentials from env (same as server uses)
        username = os.getenv("GUTAGENT_USERNAME", "")
        password = os.getenv("GUTAGENT_PASSWORD", "")

        client = TestClient(app)

        # Add auth header if credentials are set
        if username and password:
            credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
            client.headers["Authorization"] = f"Basic {credentials}"

        return client

    def test_profile_endpoint(self, client):
        """Test /api/profile returns profile data."""
        response = client.get("/api/profile")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_context_endpoint(self, client):
        """Test /api/context returns context data."""
        response = client.get("/api/context")
        assert response.status_code == 200
        data = response.json()
        assert "dynamic_context" in data

    def test_chat_endpoint_requires_message(self, client):
        """Test /api/chat requires a message field."""
        response = client.post("/api/chat", json={})
        # Should fail validation (missing required field)
        assert response.status_code == 422

    def test_chat_endpoint_accepts_message(self, client):
        """Test /api/chat accepts valid message (returns SSE stream)."""
        response = client.post(
            "/api/chat",
            json={"message": "hello", "model": "claude-haiku-4-5-20251001"}
        )
        # Should return 200 with streaming response
        # Note: actual streaming requires anthropic client, may fail without API key
        # but the endpoint should at least accept the request format
        assert response.status_code in [200, 500]  # 500 if no API key

    def test_static_files_index(self, client):
        """Test that index.html is served at root."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


# =============================================================================
# LLM PROVIDER TESTS
# =============================================================================

# Skip Claude provider tests if anthropic not installed
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

class TestLLMProviders:
    """Tests for LLM provider functionality."""

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_claude_prepare_cached_request_three_tier(self):
        """Test Claude cache control with (static, patient_data, turn_context) 3-tuple."""
        from gutagent.llm.claude_provider import ClaudeProvider

        # Create provider without API key (we won't make actual calls)
        provider = ClaudeProvider.__new__(ClaudeProvider)
        provider.cache_ttl = None  # Default 5-minute cache

        static = "You are a helpful assistant."
        patient_data = "Recent meals and vitals here."
        turn_context = "Timestamp and recent_logs here."
        tools = [{"name": "test_tool", "description": "A test", "input_schema": {"type": "object"}}]

        cached_system, cached_tools = provider._prepare_cached_request(
            (static, patient_data, turn_context), tools
        )

        # Should have 3 blocks: static (cached), patient_data (cached), turn_context (not cached)
        assert len(cached_system) == 3
        assert cached_system[0]["text"] == static
        assert cached_system[0]["cache_control"] == {"type": "ephemeral"}
        assert cached_system[1]["text"] == patient_data
        assert cached_system[1]["cache_control"] == {"type": "ephemeral"}
        assert cached_system[2]["text"] == turn_context
        assert "cache_control" not in cached_system[2]

        # Last tool should be marked for caching
        assert cached_tools[-1]["cache_control"] == {"type": "ephemeral"}

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_claude_prepare_cached_request_with_1h_ttl(self):
        """Test Claude cache control with 1-hour TTL."""
        from gutagent.llm.claude_provider import ClaudeProvider

        provider = ClaudeProvider.__new__(ClaudeProvider)
        provider.cache_ttl = "1h"

        static = "You are a helpful assistant."
        patient_data = "Recent meals."
        turn_context = "Timestamp."
        tools = []

        cached_system, cached_tools = provider._prepare_cached_request(
            (static, patient_data, turn_context), tools
        )

        # Should include TTL in cache_control for both cached blocks
        assert cached_system[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert cached_system[1]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}

    def test_llm_response_usage(self):
        """Test LLMResponse properly stores usage data."""
        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 0,
        }

        response = LLMResponse(
            content=[{"type": "text", "text": "Hello"}],
            stop_reason="end_turn",
            usage=usage,
        )

        assert response.usage == usage
        assert response.usage["input_tokens"] == 100
        assert response.usage["cache_creation_input_tokens"] == 500

    def test_llm_response_get_text(self):
        """Test LLMResponse.get_text() extracts text content."""
        response = LLMResponse(
            content=[
                {"type": "text", "text": "Hello"},
                {"type": "tool_use", "id": "1", "name": "test", "input": {}},
                {"type": "text", "text": "world"},
            ],
            stop_reason="end_turn",
        )

        # get_text joins with newline
        assert response.get_text() == "Hello\nworld"

    def test_llm_response_get_tool_calls(self):
        """Test LLMResponse.get_tool_calls() extracts tool calls."""
        response = LLMResponse(
            content=[
                {"type": "text", "text": "Let me help"},
                {"type": "tool_use", "id": "1", "name": "log_meal", "input": {"description": "lunch"}},
                {"type": "tool_use", "id": "2", "name": "log_symptom", "input": {"symptom": "headache"}},
            ],
            stop_reason="tool_use",
        )

        tool_calls = response.get_tool_calls()
        assert len(tool_calls) == 2
        assert tool_calls[0]["name"] == "log_meal"
        assert tool_calls[1]["name"] == "log_symptom"

    @pytest.mark.skipif(not HAS_ANTHROPIC, reason="anthropic not installed")
    def test_get_provider_claude(self):
        """Test get_provider returns Claude provider."""
        from gutagent.llm.claude_provider import ClaudeProvider

        # Skip if no API key (can't instantiate without it)
        if not os.getenv("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        provider = get_provider("claude")
        assert isinstance(provider, ClaudeProvider)

    def test_get_provider_invalid(self):
        """Test get_provider raises for unknown provider."""

        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("invalid_provider")


# =============================================================================
# SYSTEM PROMPT TESTS
# =============================================================================

class TestSystemPrompts:
    """Tests for system prompt construction."""

    def test_build_static_system_prompt_structure(self):
        """Test static prompt contains required sections."""
        profile = {
            "personal": {"name": "Test User", "sex": "female", "dob": "1990-01-01"},
            "conditions": ["IBS"],
        }

        prompt = build_static_system_prompt(profile)

        # Check required sections exist
        assert "GutAgent" in prompt
        assert "Patient Profile" in prompt
        assert "Test User" in prompt
        assert "IBS" in prompt
        assert "PROACTIVE LOGGING" in prompt
        assert "NUTRITION" in prompt
        assert "CORRECTIONS" in prompt
        assert "TIMESTAMPS" in prompt

    def test_build_static_system_prompt_json_profile(self):
        """Test profile is embedded as JSON."""
        profile = {
            "personal": {"name": "Jane Doe"},
            "triggers": ["gluten", "dairy"],
        }

        prompt = build_static_system_prompt(profile)

        # Profile should be JSON-formatted
        assert '"name": "Jane Doe"' in prompt
        assert '"gluten"' in prompt
        assert '"dairy"' in prompt

    def test_get_patient_data_empty_db(self):
        """Test patient data with no data returns placeholder."""
        data = get_patient_data()

        # Should return "No data logged yet." or similar
        assert isinstance(data, str)
        assert len(data) > 0

    def test_get_patient_data_with_meal(self):
        """Test patient data includes logged meal."""
        log_meal_with_nutrition(
            "breakfast",
            "test breakfast",
            items=[{"food_name": "eggs", "quantity": 2, "unit": "large"}],
            nutrition={"calories": 180, "protein": 12, "carbs": 1, "fat": 12, "fiber": 0},
        )

        data = get_patient_data()

        assert "## Meals" in data
        assert "test breakfast" in data
        assert "NUTRITION SUMMARY (1d)" in data
        assert "Daily avg: 180 cal" in data

    def test_get_patient_data_with_symptom(self):
        """Test patient data includes logged symptom."""
        log_symptom("bloating", severity=6, notes="after lunch")

        data = get_patient_data()

        assert "## Symptoms" in data
        assert "bloating" in data
        assert "(6)" in data

    def test_get_patient_data_with_vitals(self):
        """Test patient data includes logged vitals."""
        log_vital("blood_pressure", systolic=120, diastolic=80, heart_rate=72)

        data = get_patient_data()

        assert "120" in data
        assert "80" in data

    def test_get_patient_data_with_sleep(self):
        """Test patient data includes logged sleep."""
        log_sleep(hours=7.5, quality="good")

        data = get_patient_data()

        assert "## Sleep" in data
        assert "7.5h" in data

    def test_get_patient_data_with_exercise(self):
        """Test patient data includes logged exercise."""
        log_exercise("walking", duration_minutes=30)

        data = get_patient_data()

        assert "## Exercise" in data
        assert "walking" in data
        assert "30min" in data

    def test_get_patient_data_with_recipe(self):
        """Test patient data includes saved recipe names."""
        save_recipe(
            name="Test Oatmeal",
            ingredients=[{"name": "oats", "amount": 1, "unit": "cup"}],
            servings=2,
            nutrition={"calories": 150, "protein": 5, "carbs": 27, "fat": 3, "fiber": 4},
        )

        data = get_patient_data()

        assert "## Saved Recipes" in data
        assert "Test Oatmeal" in data

    def test_build_patient_data_context_structure(self):
        """Test patient data context has required header."""
        context = build_patient_data_context()

        assert "## Current Data from Patient's Records" in context

    def test_build_turn_context_structure(self):
        """Test turn context has timestamp."""
        from datetime import datetime

        context = build_turn_context()
        today = datetime.now().strftime("%Y-%m-%d")

        assert "## Current Date and Time" in context
        assert today in context

    def test_build_turn_context_with_recent_logs(self):
        """Test turn context includes recent logs string."""
        recent_logs_str = "Recently logged:\n  [meals] id:1 — eggs"

        context = build_turn_context(recent_logs_str)

        assert "Recently logged" in context
        assert "eggs" in context

    def test_patient_data_truncates_long_notes(self):
        """Test that long notes are truncated to 70 chars."""
        long_note = "A" * 100  # 100 character note
        log_symptom("headache", severity=5, notes=long_note)

        data = get_patient_data()

        # Should not contain full 100-char note
        assert "A" * 100 not in data
        # Should contain truncated version (70 chars)
        assert "A" * 70 in data


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
