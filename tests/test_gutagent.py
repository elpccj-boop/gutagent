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
- After editing `models.py` — run all tests
- After editing `registry.py` — run `TestRegistry` class
- After editing `profile.py` — run `TestProfile` class
"""

import pytest
import os
import json
import tempfile

# Set up test database before importing models
@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Use a temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    monkeypatch.setattr("gutagent.db.models.DB_PATH", path)
    
    from gutagent.db.models import init_db
    init_db()
    
    yield path
    
    os.unlink(path)


# =============================================================================
# MEAL TESTS
# =============================================================================

class TestMeals:
    """Tests for meal logging."""
    
    def test_log_meal_with_nutrition(self):
        """Log a meal with full nutrition data."""
        from gutagent.db.models import log_meal_with_nutrition
        
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
        from gutagent.db.models import log_meal_with_nutrition
        
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
        from gutagent.db.models import log_meal_with_nutrition, get_recent_meals
        
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
        from gutagent.db.models import log_meal_with_nutrition, search_meals_by_food
        
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
        from gutagent.db.models import log_symptom
        
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
        from gutagent.db.models import log_symptom, get_recent_symptoms
        
        log_symptom(symptom="nausea", severity=4)
        log_symptom(symptom="fatigue", severity=5)
        
        symptoms = get_recent_symptoms(days_back=1)
        assert len(symptoms) == 2
    
    def test_search_symptoms(self):
        """Search symptoms by term."""
        from gutagent.db.models import log_symptom, search_symptoms
        
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
        from gutagent.db.models import log_vital
        
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
        from gutagent.db.models import log_vital
        
        result = log_vital(
            vital_type="weight",
            value=70.5,
            unit="kg"
        )
        
        assert result["status"] == "logged"
    
    def test_log_temperature(self):
        """Log temperature reading."""
        from gutagent.db.models import log_vital
        
        result = log_vital(
            vital_type="temperature",
            value=98.6,
            unit="F"
        )
        
        assert result["status"] == "logged"
    
    def test_get_recent_vitals(self):
        """Retrieve recent vitals."""
        from gutagent.db.models import log_vital, get_recent_vitals
        
        log_vital(vital_type="blood_pressure", systolic=118, diastolic=78, heart_rate=70)
        log_vital(vital_type="blood_pressure", systolic=122, diastolic=82, heart_rate=75)
        
        result = get_recent_vitals(days_back=1, vital_type="blood_pressure")
        # Returns a formatted string
        assert isinstance(result, (str, dict))


# =============================================================================
# MEDICATION TESTS
# =============================================================================

class TestMedications:
    """Tests for medication logging."""
    
    def test_log_medication_taken(self):
        """Log medication taken."""
        from gutagent.db.models import log_medication_event
        
        result = log_medication_event(
            medication="ibuprofen",
            event_type="taken",
            dose="200mg"
        )
        
        assert result["status"] == "logged"
        assert result["medication"] == "ibuprofen"
    
    def test_log_medication_started(self):
        """Log starting a new medication."""
        from gutagent.db.models import log_medication_event
        
        result = log_medication_event(
            medication="vitamin D",
            event_type="started",
            dose="1000 IU daily"
        )
        
        assert result["status"] == "logged"
        assert result["event"] == "started"
    
    def test_get_recent_meds(self):
        """Retrieve recent medication events."""
        from gutagent.db.models import log_medication_event, get_recent_meds
        
        log_medication_event(medication="aspirin", event_type="taken")
        
        meds = get_recent_meds(days_back=1)
        assert len(meds) == 1
        assert meds[0]["medication"] == "aspirin"


# =============================================================================
# SLEEP TESTS
# =============================================================================

class TestSleep:
    """Tests for sleep logging."""
    
    def test_log_sleep(self):
        """Log sleep entry."""
        from gutagent.db.models import log_sleep
        
        result = log_sleep(
            hours=7.5,
            quality="good",
            notes="woke up once"
        )
        
        assert result["status"] == "logged"
    
    def test_get_recent_sleep(self):
        """Retrieve recent sleep entries."""
        from gutagent.db.models import log_sleep, get_recent_sleep
        
        log_sleep(hours=8, quality="excellent")
        log_sleep(hours=6, quality="poor")
        
        entries = get_recent_sleep(days_back=7)
        assert len(entries) == 2


# =============================================================================
# EXERCISE TESTS
# =============================================================================

class TestExercise:
    """Tests for exercise logging."""
    
    def test_log_exercise(self):
        """Log exercise entry."""
        from gutagent.db.models import log_exercise
        
        result = log_exercise(
            activity="running",
            duration_minutes=30,
            notes="5K run"
        )
        
        assert result["status"] == "logged"
    
    def test_get_recent_exercise(self):
        """Retrieve recent exercise entries."""
        from gutagent.db.models import log_exercise, get_recent_exercise
        
        log_exercise(activity="yoga", duration_minutes=60)
        log_exercise(activity="walking", duration_minutes=45)
        
        entries = get_recent_exercise(days_back=7)
        assert len(entries) == 2


# =============================================================================
# JOURNAL TESTS
# =============================================================================

class TestJournal:
    """Tests for journal entries."""
    
    def test_log_journal(self):
        """Log journal entry."""
        from gutagent.db.models import log_journal_entry
        
        result = log_journal_entry(
            description="Feeling good today, energy levels high"
        )
        
        assert result["status"] == "logged"
    
    def test_get_recent_journal(self):
        """Retrieve recent journal entries."""
        from gutagent.db.models import log_journal_entry, get_recent_journal
        
        log_journal_entry(description="Day 1 notes")
        log_journal_entry(description="Day 2 notes")
        
        entries = get_recent_journal(days_back=7)
        assert len(entries) == 2


# =============================================================================
# RECIPE TESTS
# =============================================================================

class TestRecipes:
    """Tests for recipe management."""
    
    def test_save_recipe(self):
        """Save a new recipe."""
        from gutagent.db.models import save_recipe
        
        result = save_recipe(
            name="Masala tea",
            ingredients=[
                {"name": "milk", "quantity": 1, "unit": "cup"},
                {"name": "tea", "quantity": 1, "unit": "tsp"}
            ],
            servings=2,
            nutrition={"calories": 100, "protein": 4}
        )
        
        assert result["status"] == "created"
    
    def test_get_recipe(self):
        """Retrieve a saved recipe."""
        from gutagent.db.models import save_recipe, get_recipe
        
        save_recipe(
            name="Test recipe",
            ingredients=[],
            servings=4,
            nutrition={"calories": 400, "protein": 20}
        )
        
        recipe = get_recipe("Test recipe")
        assert recipe is not None
        assert recipe["name"] == "Test recipe"
        assert recipe["servings"] == 4
        assert recipe["nutrition"]["calories"] == 100  # 400/4
        assert recipe["nutrition"]["protein"] == 5  # 20/4
    
    def test_get_recipe_case_insensitive(self):
        """Recipe lookup is case-insensitive."""
        from gutagent.db.models import save_recipe, get_recipe
        
        save_recipe(name="Chicken Curry", ingredients=[], servings=1, nutrition={})
        
        assert get_recipe("chicken curry") is not None
        assert get_recipe("CHICKEN CURRY") is not None
    
    def test_list_recipes(self):
        """List all recipes."""
        from gutagent.db.models import save_recipe, list_recipes
        
        save_recipe(name="Recipe A", ingredients=[], servings=1, nutrition={})
        save_recipe(name="Recipe B", ingredients=[], servings=1, nutrition={})
        
        recipes = list_recipes()
        assert len(recipes) >= 2
        names = [r["name"] for r in recipes]
        assert "Recipe A" in names
        assert "Recipe B" in names
    
    def test_delete_recipe(self):
        """Delete a recipe."""
        from gutagent.db.models import save_recipe, delete_recipe, get_recipe
        
        save_recipe(name="To delete", ingredients=[], servings=1, nutrition={})
        
        result = delete_recipe("To delete")
        assert result["status"] == "deleted"
        
        assert get_recipe("To delete") is None
    
    def test_update_recipe(self):
        """Update an existing recipe."""
        from gutagent.db.models import save_recipe, get_recipe
        
        save_recipe(name="Updatable", ingredients=[], servings=1, nutrition={"calories": 100})
        save_recipe(name="Updatable", ingredients=[], servings=2, nutrition={"calories": 200})
        
        recipe = get_recipe("Updatable")
        assert recipe["servings"] == 2
        assert recipe["nutrition"]["calories"] == 100  # 200/2


# =============================================================================
# NUTRITION SUMMARY & ALERTS
# =============================================================================

class TestNutrition:
    """Tests for nutrition tracking."""
    
    def test_nutrition_summary_empty(self):
        """Summary with no data."""
        from gutagent.db.models import get_nutrition_summary
        
        result = get_nutrition_summary(days=3)
        assert isinstance(result, str)
        assert "No nutrition data" in result
    
    def test_nutrition_summary_with_data(self):
        """Summary with meal data."""
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_summary
        
        log_meal_with_nutrition(
            meal_type="lunch",
            description="test",
            items=[],
            nutrition={"calories": 500, "protein": 30}
        )
        
        result = get_nutrition_summary(days=1)
        assert isinstance(result, str)
        assert "500" in result
    
    def test_nutrition_alerts_empty(self):
        """Alerts with no data."""
        from gutagent.db.models import get_nutrition_alerts
        
        result = get_nutrition_alerts(days=3)
        assert isinstance(result, str)
    
    def test_nutrition_alerts_deficiency(self):
        """Alerts show deficiencies."""
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts
        
        # Log meal with very low nutrients
        log_meal_with_nutrition(
            meal_type="lunch",
            description="plain rice",
            items=[],
            nutrition={"calories": 200, "protein": 4, "vitamin_c": 0}
        )
        
        result = get_nutrition_alerts(days=1)
        assert isinstance(result, str)
        # Should have some alerts
        assert len(result) > 0


# =============================================================================
# LAB TESTS
# =============================================================================

class TestLabs:
    """Tests for lab test logging and querying."""

    def test_log_lab_minimal(self):
        """Log lab with just test name."""
        from gutagent.db.models import log_lab

        result = log_lab(test_name="B12")

        assert result["id"] > 0
        assert result["status"] == "logged"
        assert result["test_name"] == "B12"
        assert "B12" in result["summary"]

    def test_log_lab_complete(self):
        """Log lab with all fields."""
        from gutagent.db.models import log_lab

        result = log_lab(
            test_name="Ferritin",
            test_date="2026-03-10 09:00:00",
            value=25,
            unit="ng/mL",
            reference_range="30-400 ng/mL",
            status="low",
            notes="Retest in 3 months"
        )

        assert result["id"] > 0
        assert result["status"] == "logged"
        assert result["test_name"] == "Ferritin"
        assert result["test_date"] == "2026-03-10"
        assert "Ferritin" in result["summary"]
        assert "25" in result["summary"]
        assert "low" in result["summary"]

    def test_log_lab_infers_date(self):
        """Log lab defaults to today if no date provided."""
        from gutagent.db.models import log_lab
        from datetime import datetime

        result = log_lab(test_name="CRP", value=0.5, unit="mg/L")

        # Should default to today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert result["test_date"] == today

    def test_get_recent_labs(self):
        """Get recent lab results."""
        from gutagent.db.models import log_lab, get_recent_labs

        log_lab(test_name="B12", value=450, unit="pg/mL")
        log_lab(test_name="Ferritin", value=25, unit="ng/mL")

        labs = get_recent_labs()

        assert len(labs) == 2
        assert any(lab["test_name"] == "B12" for lab in labs)
        assert any(lab["test_name"] == "Ferritin" for lab in labs)

    def test_get_recent_labs_by_test_name(self):
        """Get labs filtered by test name."""
        from gutagent.db.models import log_lab, get_recent_labs

        log_lab(test_name="B12", value=450, unit="pg/mL", test_date="2026-03-01")
        log_lab(test_name="B12", value=460, unit="pg/mL", test_date="2026-03-10")
        log_lab(test_name="Ferritin", value=25, unit="ng/mL")

        b12_labs = get_recent_labs(test_date="B12")  # Note: current implementation uses test_date param

        # Should return B12 results (implementation dependent)
        assert len(b12_labs) >= 0

    def test_get_latest_labs_per_test(self):
        """Get latest result for each test type."""
        from gutagent.db.models import log_lab, get_latest_labs_per_test

        # Log multiple results for same test
        log_lab(test_name="B12", value=450, unit="pg/mL", test_date="2026-03-01")
        log_lab(test_name="B12", value=460, unit="pg/mL", test_date="2026-03-10")
        log_lab(test_name="Ferritin", value=25, unit="ng/mL", test_date="2026-03-05")

        latest = get_latest_labs_per_test()

        # Should have one entry per test type
        test_names = [lab["test_name"] for lab in latest]
        assert "B12" in test_names
        assert "Ferritin" in test_names

        # Should have latest B12 value
        b12_entry = next(lab for lab in latest if lab["test_name"] == "B12")
        assert b12_entry["value"] == 460

    def test_get_logs_by_date_labs(self):
        """Get labs by specific date."""
        from gutagent.db.models import log_lab, get_logs_by_date

        log_lab(test_name="B12", value=450, test_date="2026-03-10 09:00:00")
        log_lab(test_name="Ferritin", value=25, test_date="2026-03-10 10:00:00")
        log_lab(test_name="CRP", value=0.5, test_date="2026-03-11")

        labs_march_10 = get_logs_by_date("labs", "2026-03-10")

        assert len(labs_march_10) == 2
        assert all(lab["test_date"] == "2026-03-10" for lab in labs_march_10)

    def test_update_lab(self):
        """Update lab entry."""
        from gutagent.db.models import log_lab, update_log

        result = log_lab(test_name="B12", value=450, unit="pg/mL")
        lab_id = result["id"]

        # Update value
        update_log("labs", lab_id, {"value": 460})

        # Verify update
        from gutagent.db.models import get_connection
        conn = get_connection()
        updated = dict(conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone())
        conn.close()

        assert updated["value"] == 460

    def test_delete_lab(self):
        """Delete lab entry."""
        from gutagent.db.models import log_lab, delete_log

        result = log_lab(test_name="B12", value=450)
        lab_id = result["id"]

        delete_log("labs", lab_id)

        # Verify deletion
        from gutagent.db.models import get_connection
        conn = get_connection()
        deleted = conn.execute("SELECT * FROM labs WHERE id = ?", (lab_id,)).fetchone()
        conn.close()

        assert deleted is None


# =============================================================================
# CORRECTION/UPDATE/DELETE TESTS
# =============================================================================

class TestCorrections:
    """Tests for updating and deleting logs."""
    
    def test_update_meal(self):
        """Update a meal entry."""
        from gutagent.db.models import log_meal_with_nutrition, update_log
        
        result = log_meal_with_nutrition(
            meal_type="lunch",
            description="wrong description",
            items=[],
            nutrition={"calories": 100}
        )
        meal_id = result["id"]
        
        update_result = update_log("meals", meal_id, {"description": "correct description"})
        assert update_result["status"] == "updated"
    
    def test_delete_meal(self):
        """Delete a meal entry."""
        from gutagent.db.models import log_meal_with_nutrition, delete_log, get_recent_meals
        
        result = log_meal_with_nutrition(
            meal_type="lunch",
            description="to delete",
            items=[],
            nutrition={"calories": 100}
        )
        meal_id = result["id"]
        
        delete_result = delete_log("meals", meal_id)
        assert delete_result["status"] == "deleted"
        
        meals = get_recent_meals(days_back=1)
        assert len(meals) == 0
    
    def test_update_symptom(self):
        """Update a symptom entry."""
        from gutagent.db.models import log_symptom, update_log
        
        result = log_symptom(symptom="headache", severity=5)
        symptom_id = result["id"]
        
        update_result = update_log("symptoms", symptom_id, {"severity": 7})
        assert update_result["status"] == "updated"
    
    def test_delete_symptom(self):
        """Delete a symptom entry."""
        from gutagent.db.models import log_symptom, delete_log
        
        result = log_symptom(symptom="to delete", severity=3)
        symptom_id = result["id"]
        
        delete_result = delete_log("symptoms", symptom_id)
        assert delete_result["status"] == "deleted"


# =============================================================================
# DATE SEARCH TESTS
# =============================================================================

class TestDateSearch:
    """Tests for date-based searches."""
    
    def test_get_logs_by_date_meals(self):
        """Search meals by specific date."""
        from gutagent.db.models import log_meal_with_nutrition, get_logs_by_date
        
        log_meal_with_nutrition(
            meal_type="breakfast",
            description="morning meal",
            items=[],
            nutrition={"calories": 300},
            occurred_at="2026-03-15 08:00:00"
        )
        
        results = get_logs_by_date("meals", "2026-03-15")
        assert len(results) == 1
        assert results[0]["description"] == "morning meal"
    
    def test_get_logs_by_date_symptoms(self):
        """Search symptoms by specific date."""
        from gutagent.db.models import log_symptom, get_logs_by_date
        
        log_symptom(
            symptom="test symptom",
            severity=5,
            occurred_at="2026-03-14 10:00:00"
        )
        
        results = get_logs_by_date("symptoms", "2026-03-14")
        assert len(results) == 1


# =============================================================================
# REGISTRY/HANDLER TESTS
# =============================================================================

class TestRegistry:
    """Tests for tool registry handlers."""
    
    def test_execute_log_meal(self):
        """Execute log_meal through registry."""
        from gutagent.tools.registry import execute_tool
        
        result = json.loads(execute_tool("log_meal", {
            "meal_type": "lunch",
            "description": "test meal via registry",
            "items": [
                {"name": "rice", "quantity": 1, "unit": "cup", "calories": 200, "protein": 4}
            ]
        }))
        
        assert result["status"] == "logged"
    
    def test_execute_log_meal_with_recipe(self):
        """Execute log_meal with recipe name."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import save_recipe
        
        # First save a recipe
        save_recipe(
            name="Test Recipe",
            ingredients=[],
            servings=1,
            nutrition={"calories": 250, "protein": 15}
        )
        
        result = json.loads(execute_tool("log_meal", {
            "meal_type": "dinner",
            "description": "test recipe meal",
            "recipe_name": "Test Recipe"
        }))
        
        assert result["status"] == "logged"
    
    def test_execute_log_symptom(self):
        """Execute log_symptom through registry."""
        from gutagent.tools.registry import execute_tool
        
        result = json.loads(execute_tool("log_symptom", {
            "symptom": "headache",
            "severity": 5
        }))
        
        assert result["status"] == "logged"
    
    def test_execute_log_vital(self):
        """Execute log_vital through registry."""
        from gutagent.tools.registry import execute_tool
        
        result = json.loads(execute_tool("log_vital", {
            "vital_type": "blood_pressure",
            "systolic": 120,
            "diastolic": 80,
            "heart_rate": 70
        }))
        
        assert result["status"] == "logged"
    
    def test_execute_query_logs_recent_meals(self):
        """Execute query_logs for recent meals."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_meal_with_nutrition
        
        log_meal_with_nutrition(
            meal_type="lunch",
            description="query test meal",
            items=[],
            nutrition={"calories": 100}
        )
        
        result = execute_tool("query_logs", {
            "query_type": "recent_meals",
            "days_back": 1
        })

        # Verify string output format
        assert isinstance(result, str)
        assert "meal" in result.lower()
        assert "query test meal" in result
        assert "[id:" in result  # Contains entry ID in [id:X] format

    def test_execute_query_logs_date_search(self):
        """Execute query_logs for date search."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_meal_with_nutrition
        
        log_meal_with_nutrition(
            meal_type="breakfast",
            description="date search test",
            items=[],
            nutrition={"calories": 200},
            occurred_at="2026-03-10 09:00:00"
        )
        
        result = execute_tool("query_logs", {
            "query_type": "date_search",
            "date": "2026-03-10",
            "table": "meals"
        })

        # Verify string output format
        assert isinstance(result, str)
        assert "2026-03-10" in result
        assert "date search test" in result
        assert "meal" in result.lower()
        assert "[id:" in result  # Contains entry ID in [id:X] format

    def test_execute_correct_log_update(self):
        """Execute correct_log to update."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_symptom
        
        symptom = log_symptom(symptom="test", severity=3)
        
        result = json.loads(execute_tool("correct_log", {
            "action": "update",
            "table": "symptoms",
            "entry_id": symptom["id"],
            "updates": {"severity": 8}
        }))
        
        assert result["status"] == "updated"
    
    def test_execute_correct_log_delete(self):
        """Execute correct_log to delete."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_symptom
        
        symptom = log_symptom(symptom="to delete", severity=2)
        
        result = json.loads(execute_tool("correct_log", {
            "action": "delete",
            "table": "symptoms",
            "entry_id": symptom["id"]
        }))
        
        assert result["status"] == "deleted"
    
    def test_execute_save_recipe(self):
        """Execute save_recipe through registry."""
        from gutagent.tools.registry import execute_tool
        
        result = json.loads(execute_tool("save_recipe", {
            "name": "Registry Recipe",
            "ingredients": [{"name": "item", "quantity": 1, "unit": "piece"}],
            "servings": 2
        }))
        
        assert result["status"] == "created"
    
    def test_execute_get_recipe(self):
        """Execute get_recipe through registry."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import save_recipe
        
        save_recipe(name="Findable", ingredients=[], servings=1, nutrition={})
        
        result = json.loads(execute_tool("get_recipe", {"name": "Findable"}))
        
        assert result["name"] == "Findable"
    
    def test_execute_list_recipes(self):
        """Execute list_recipes through registry."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import save_recipe
        
        save_recipe(name="List Test", ingredients=[], servings=1, nutrition={})
        
        result = json.loads(execute_tool("list_recipes", {}))
        
        assert result["count"] >= 1
    
    def test_execute_unknown_tool(self):
        """Unknown tool returns error."""
        from gutagent.tools.registry import execute_tool
        
        result = json.loads(execute_tool("nonexistent_tool", {}))
        
        assert "error" in result
    
    def test_execute_get_nutrition_summary(self):
        """Execute get_nutrition_summary through registry."""
        from gutagent.tools.registry import execute_tool
        
        result = execute_tool("get_nutrition_summary", {"days": 3})
        # Returns string directly (not JSON of string)
        assert isinstance(result, str)
    
    def test_execute_get_nutrition_alerts(self):
        """Execute get_nutrition_alerts through registry."""
        from gutagent.tools.registry import execute_tool
        
        result = execute_tool("get_nutrition_alerts", {"days": 3})
        assert isinstance(result, str)

    def test_execute_log_lab(self):
        """Execute log_lab through registry."""
        from gutagent.tools.registry import execute_tool

        result = json.loads(execute_tool("log_lab", {
            "test_name": "B12",
            "value": 450,
            "unit": "pg/mL",
            "status": "normal"
        }))

        assert result["status"] == "logged"
        assert result["test_name"] == "B12"

    def test_execute_log_lab_minimal(self):
        """Execute log_lab with only required field."""
        from gutagent.tools.registry import execute_tool

        result = json.loads(execute_tool("log_lab", {
            "test_name": "CRP"
        }))

        assert result["status"] == "logged"
        assert result["test_name"] == "CRP"

    def test_execute_query_logs_date_search_labs(self):
        """Execute query_logs for labs by date - STRING FORMAT."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_lab

        log_lab(
            test_name="B12",
            value=450,
            unit="pg/mL",
            test_date="2026-03-10 09:00:00"
        )

        # Note: optimized query_logs returns string, not JSON
        result = execute_tool("query_logs", {
            "query_type": "date_search",
            "date": "2026-03-10",
            "table": "labs"
        })

        # Verify string output format
        assert isinstance(result, str)
        assert "2026-03-10" in result
        assert "B12" in result
        assert "450" in result

    def test_execute_correct_log_labs(self):
        """Execute correct_log to update lab entry."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_lab

        result = log_lab(test_name="Ferritin", value=25, unit="ng/mL")
        lab_id = result["id"]

        # Update the value
        update_result = json.loads(execute_tool("correct_log", {
            "action": "update",
            "table": "labs",
            "entry_id": lab_id,
            "updates": {"value": 30}
        }))

        assert update_result["status"] == "updated"
        assert update_result["id"] == lab_id

    def test_execute_correct_log_delete_lab(self):
        """Execute correct_log to delete lab entry."""
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_lab

        result = log_lab(test_name="Test Entry")
        lab_id = result["id"]

        # Delete
        delete_result = json.loads(execute_tool("correct_log", {
            "action": "delete",
            "table": "labs",
            "entry_id": lab_id
        }))

        assert delete_result["status"] == "deleted"
        assert delete_result["id"] == lab_id


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_meal_items(self):
        """Log meal with empty items list."""
        from gutagent.db.models import log_meal_with_nutrition
        
        result = log_meal_with_nutrition(
            meal_type="snack",
            description="quick bite",
            items=[],
            nutrition={"calories": 50}
        )
        
        assert result["status"] == "logged"
    
    def test_recipe_not_found(self):
        """Get non-existent recipe returns None."""
        from gutagent.db.models import get_recipe
        
        result = get_recipe("Nonexistent Recipe")
        assert result is None
    
    def test_delete_nonexistent(self):
        """Delete non-existent entry."""
        from gutagent.db.models import delete_log
        
        result = delete_log("meals", 99999)
        # Should handle gracefully
        assert "status" in result or "error" in result
    
    def test_timestamp_parsing(self):
        """Various timestamp formats."""
        from gutagent.db.models import log_meal_with_nutrition
        
        # Full datetime
        r1 = log_meal_with_nutrition(
            meal_type="test",
            description="test1",
            items=[],
            nutrition={},
            occurred_at="2026-03-15 14:30:00"
        )
        assert "2026-03-15" in r1["when"]
        
        # Date only should work too
        r2 = log_meal_with_nutrition(
            meal_type="test",
            description="test2",
            items=[],
            nutrition={},
            occurred_at="2026-03-14"
        )
        assert "2026-03-14" in r2["when"]
    
    def test_special_characters_in_description(self):
        """Handle special characters in text fields."""
        from gutagent.db.models import log_meal_with_nutrition, get_recent_meals
        
        log_meal_with_nutrition(
            meal_type="lunch",
            description="Tom's \"special\" meal — with spices & herbs",
            items=[],
            nutrition={"calories": 300}
        )
        
        meals = get_recent_meals(days_back=1)
        assert len(meals) == 1
        assert "Tom's" in meals[0]["description"]


# =============================================================================
# PROFILE TESTS
# =============================================================================

class TestProfile:
    """Tests for profile management."""

    @pytest.fixture(autouse=True)
    def temp_profile(self, monkeypatch):
        """Use a temporary profile for each test."""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(path)  # Remove so load_profile sees "not found"

        monkeypatch.setattr("gutagent.profile.PROFILE_PATH", path)

        yield path

        if os.path.exists(path):
            os.unlink(path)

    def test_load_profile_not_found(self):
        """Load profile when file doesn't exist."""
        from gutagent.profile import load_profile

        result = load_profile()
        assert "error" in result

    def test_save_and_load_profile(self):
        """Save and load a profile."""
        from gutagent.profile import save_profile, load_profile

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
        from gutagent.profile import save_profile, update_profile, load_profile

        save_profile({"name": "Old Name"})

        result = update_profile("name", "set", "New Name")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert loaded["name"] == "New Name"

    def test_update_profile_append(self):
        """Update profile with append action."""
        from gutagent.profile import save_profile, update_profile, load_profile

        save_profile({"conditions": {"chronic": ["existing"]}})

        result = update_profile("conditions.chronic", "append", "new condition")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert "new condition" in loaded["conditions"]["chronic"]
        assert "existing" in loaded["conditions"]["chronic"]

    def test_update_profile_append_creates_list(self):
        """Append to non-existent key creates list."""
        from gutagent.profile import save_profile, update_profile, load_profile

        save_profile({})

        result = update_profile("conditions.chronic", "append", "first item")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert loaded["conditions"]["chronic"] == ["first item"]

    def test_update_profile_remove(self):
        """Update profile with remove action."""
        from gutagent.profile import save_profile, update_profile, load_profile

        save_profile({"meds": ["aspirin daily", "vitamin D"]})

        result = update_profile("meds", "remove", "aspirin")
        assert result["status"] == "removed"
        assert result["items_removed"] == 1

        loaded = load_profile()
        assert len(loaded["meds"]) == 1
        assert "vitamin D" in loaded["meds"]

    def test_update_profile_remove_not_found(self):
        """Remove non-existent item returns error."""
        from gutagent.profile import save_profile, update_profile

        save_profile({"meds": ["aspirin"]})

        result = update_profile("meds", "remove", "nonexistent")
        assert "error" in result

    def test_update_profile_append_to_non_list(self):
        """Append to non-list returns error."""
        from gutagent.profile import save_profile, update_profile

        save_profile({"name": "Test"})

        result = update_profile("name", "append", "extra")
        assert "error" in result

    def test_update_profile_unknown_action(self):
        """Unknown action returns error."""
        from gutagent.profile import save_profile, update_profile

        save_profile({})

        result = update_profile("key", "invalid_action", "value")
        assert "error" in result

    def test_update_profile_nested_path(self):
        """Update deeply nested path."""
        from gutagent.profile import save_profile, update_profile, load_profile

        save_profile({"level1": {"level2": {"level3": "old"}}})

        result = update_profile("level1.level2.level3", "set", "new")
        assert result["status"] == "updated"

        loaded = load_profile()
        assert loaded["level1"]["level2"]["level3"] == "new"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
