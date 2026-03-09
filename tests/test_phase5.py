"""Tests for Phase 5: Nutrition Tracking (Claude-estimated)."""

import pytest
import os
import tempfile
import json

# Monkeypatch DB_PATH before importing models
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


class TestMealWithNutrition:
    """Test logging meals with nutrition data."""
    
    def test_log_meal_with_nutrition(self):
        from gutagent.db.models import log_meal_with_nutrition, get_connection
        
        items = [
            {"food_name": "eggs", "quantity": 2, "unit": "piece", "is_spice": False},
            {"food_name": "toast", "quantity": 2, "unit": "slice", "is_spice": False},
        ]
        nutrition = {
            "calories": 340,
            "protein": 18,
            "carbs": 30,
            "fat": 16,
            "fiber": 2,
            "vitamin_b12": 1.2,
            "vitamin_d": 1.0,
            "iron": 2.5,
        }
        
        result = log_meal_with_nutrition(
            meal_type="breakfast",
            description="eggs and toast",
            items=items,
            nutrition=nutrition,
        )
        
        assert result["status"] == "logged"
        assert result["items_count"] == 2
        assert result["nutrition"]["calories"] == 340
        
        # Verify database
        conn = get_connection()
        
        # Check meal_items
        items_rows = conn.execute(
            "SELECT * FROM meal_items WHERE meal_id = ?", (result["id"],)
        ).fetchall()
        assert len(items_rows) == 2
        
        # Check meal_nutrition
        nutrition_row = conn.execute(
            "SELECT * FROM meal_nutrition WHERE meal_id = ?", (result["id"],)
        ).fetchone()
        assert nutrition_row["calories"] == 340
        assert nutrition_row["protein"] == 18
        assert nutrition_row["vitamin_b12"] == 1.2
        
        conn.close()
    
    def test_log_meal_with_spices(self):
        from gutagent.db.models import log_meal_with_nutrition, get_connection
        
        items = [
            {"food_name": "chicken", "quantity": 150, "unit": "g", "is_spice": False},
            {"food_name": "turmeric", "quantity": 1, "unit": "tsp", "is_spice": True},
            {"food_name": "cumin", "quantity": 1, "unit": "tsp", "is_spice": True},
        ]
        nutrition = {"calories": 250, "protein": 30, "carbs": 2, "fat": 12, "fiber": 1}
        
        result = log_meal_with_nutrition(
            meal_type="lunch",
            description="chicken curry",
            items=items,
            nutrition=nutrition,
        )
        
        conn = get_connection()
        spice_count = conn.execute(
            "SELECT COUNT(*) FROM meal_items WHERE meal_id = ? AND is_spice = 1",
            (result["id"],)
        ).fetchone()[0]
        assert spice_count == 2
        conn.close()
    
    def test_log_meal_with_occurred_at(self):
        from gutagent.db.models import log_meal_with_nutrition, get_connection
        
        result = log_meal_with_nutrition(
            meal_type="dinner",
            description="rice and dal",
            items=[{"food_name": "rice", "quantity": 1, "unit": "cup"}],
            nutrition={"calories": 200, "protein": 5, "carbs": 45, "fat": 0, "fiber": 1},
            occurred_at="2026-03-07 19:00:00",
        )
        
        assert result["when"] == "2026-03-07 19:00:00"
        
        conn = get_connection()
        row = conn.execute("SELECT occurred_at FROM meals WHERE id = ?", (result["id"],)).fetchone()
        assert row["occurred_at"] == "2026-03-07 19:00:00"
        conn.close()


class TestRecipes:
    """Test recipe CRUD operations."""
    
    def test_save_recipe(self):
        from gutagent.db.models import save_recipe, get_recipe
        
        ingredients = [
            {"name": "toor dal", "quantity": 1, "unit": "cup", "calories": 200, "protein": 12, "carbs": 35, "fat": 1, "fiber": 8},
            {"name": "tomato", "quantity": 2, "unit": "piece", "calories": 40, "protein": 2, "carbs": 8, "fat": 0, "fiber": 2},
            {"name": "turmeric", "quantity": 1, "unit": "tsp", "calories": 8, "protein": 0, "carbs": 2, "fat": 0, "fiber": 0, "is_spice": True},
        ]
        
        result = save_recipe("Dal Tadka", ingredients, notes="Family recipe")
        assert result["status"] == "created"
        assert result["ingredients_count"] == 3
        
        # Retrieve and verify
        recipe = get_recipe("dal tadka")  # case-insensitive
        assert recipe is not None
        assert recipe["name"] == "Dal Tadka"
        assert len(recipe["ingredients"]) == 3
        assert recipe["notes"] == "Family recipe"
    
    def test_update_recipe(self):
        from gutagent.db.models import save_recipe, get_recipe
        
        # Create
        save_recipe("Test Recipe", [{"name": "item1", "calories": 100, "protein": 5, "carbs": 10, "fat": 3}])
        
        # Update
        result = save_recipe("test recipe", [
            {"name": "item1", "calories": 100, "protein": 5, "carbs": 10, "fat": 3},
            {"name": "item2", "calories": 50, "protein": 2, "carbs": 8, "fat": 1},
        ])
        assert result["status"] == "updated"
        assert result["ingredients_count"] == 2
        
        recipe = get_recipe("Test Recipe")
        assert len(recipe["ingredients"]) == 2
    
    def test_list_recipes(self):
        from gutagent.db.models import save_recipe, list_recipes
        
        save_recipe("Recipe A", [{"name": "x", "calories": 10, "protein": 1, "carbs": 1, "fat": 0}])
        save_recipe("Recipe B", [{"name": "y", "calories": 20, "protein": 2, "carbs": 2, "fat": 0}])
        
        recipes = list_recipes()
        assert len(recipes) == 2
        names = [r["name"] for r in recipes]
        assert "Recipe A" in names
        assert "Recipe B" in names
    
    def test_delete_recipe(self):
        from gutagent.db.models import save_recipe, delete_recipe, get_recipe
        
        save_recipe("To Delete", [{"name": "x", "calories": 10, "protein": 1, "carbs": 1, "fat": 0}])
        
        result = delete_recipe("to delete")
        assert result["status"] == "deleted"
        
        assert get_recipe("To Delete") is None
    
    def test_delete_nonexistent_recipe(self):
        from gutagent.db.models import delete_recipe
        
        result = delete_recipe("Does Not Exist")
        assert result["status"] == "not_found"


class TestNutritionSummary:
    """Test nutrition summary calculations."""
    
    def test_empty_summary(self):
        from gutagent.db.models import get_nutrition_summary
        
        result = get_nutrition_summary(days=7)
        assert result["days_with_data"] == 0
    
    def test_summary_aggregation(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_summary
        
        # Log two meals
        log_meal_with_nutrition(
            meal_type="breakfast",
            description="meal 1",
            items=[{"food_name": "food1"}],
            nutrition={"calories": 300, "protein": 20, "carbs": 30, "fat": 10, "fiber": 5, "iron": 3},
        )
        log_meal_with_nutrition(
            meal_type="lunch",
            description="meal 2",
            items=[{"food_name": "food2"}],
            nutrition={"calories": 500, "protein": 30, "carbs": 50, "fat": 20, "fiber": 8, "iron": 5},
        )
        
        result = get_nutrition_summary(days=3)
        
        assert result["days_with_data"] == 1  # Both meals on same day
        assert result["totals"]["calories"] == 800
        assert result["totals"]["protein"] == 50
        assert result["totals"]["iron"] == 8
        assert result["daily_averages"]["calories"] == 800  # 1 day
    
    def test_summary_multiple_days(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_summary
        
        # Day 1
        log_meal_with_nutrition(
            meal_type="breakfast",
            description="day 1 meal",
            items=[{"food_name": "food"}],
            nutrition={"calories": 400, "protein": 20, "carbs": 40, "fat": 15, "fiber": 5},
            occurred_at="2026-03-07 08:00:00",
        )
        
        # Day 2
        log_meal_with_nutrition(
            meal_type="breakfast",
            description="day 2 meal",
            items=[{"food_name": "food"}],
            nutrition={"calories": 600, "protein": 30, "carbs": 60, "fat": 20, "fiber": 10},
            occurred_at="2026-03-08 08:00:00",
        )
        
        result = get_nutrition_summary(days=7)
        
        assert result["days_with_data"] == 2
        assert result["totals"]["calories"] == 1000
        assert result["daily_averages"]["calories"] == 500  # 1000 / 2 days


class TestNutritionAlerts:
    """Test nutrition deficiency and excess alerts."""
    
    def test_no_alerts_when_no_data(self):
        from gutagent.db.models import get_nutrition_alerts
        
        alerts = get_nutrition_alerts(days=3)
        assert alerts == []
    
    def test_low_nutrient_alert(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts
        
        # Log meal with all nutrients at 100% except iron at 25%
        log_meal_with_nutrition(
            meal_type="lunch",
            description="low iron meal",
            items=[{"food_name": "food"}],
            nutrition={
                "calories": 500,
                "protein": 20,
                "carbs": 60,
                "fat": 15,
                "fiber": 25,       # 100% of target
                "iron": 2,         # 25% of target (8mg) - should alert
                "vitamin_b12": 3,  # 125% of target
                "vitamin_d": 15,   # 100% of target
                "folate": 400,     # 100%
                "zinc": 11,        # 100%
                "magnesium": 400,  # 100%
                "calcium": 1000,   # 100%
                "potassium": 2600, # 100%
                "omega_3": 1.6,    # 100%
                "vitamin_a": 900,  # 100%
                "vitamin_c": 90,   # 100%
            },
        )
        
        alerts = get_nutrition_alerts(days=3)
        
        # Should have exactly one alert for iron (all others at 100%)
        deficiency_alerts = [a for a in alerts if a["type"] == "deficiency"]
        assert len(deficiency_alerts) == 1
        assert deficiency_alerts[0]["nutrient"] == "iron"
        assert deficiency_alerts[0]["severity"] == "very_low"  # 25% is < 50%
        assert deficiency_alerts[0]["percent_of_rda"] == 25.0
    
    def test_missing_nutrients_alert(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts

        # Log meal with only macros - all micronutrients missing (0%)
        log_meal_with_nutrition(
            meal_type="lunch",
            description="no micronutrients",
            items=[{"food_name": "food"}],
            nutrition={
                "calories": 500,
                "protein": 20,
                "carbs": 60,
                "fat": 15,
                "fiber": 5,  # 20% - should alert
                # All micronutrients default to 0 - should all alert
            },
        )

        alerts = get_nutrition_alerts(days=3)
        deficiency_alerts = [a for a in alerts if a["type"] == "deficiency"]

        # Should have alerts for fiber + all 11 micronutrients = 12 alerts
        assert len(deficiency_alerts) == 12

        nutrients_with_alerts = [a["nutrient"] for a in deficiency_alerts]
        assert "fiber" in nutrients_with_alerts
        assert "vitamin_b12" in nutrients_with_alerts
        assert "zinc" in nutrients_with_alerts
        assert "omega_3" in nutrients_with_alerts
        assert "potassium" in nutrients_with_alerts

        # All should be very_low (0% or 20%)
        for alert in deficiency_alerts:
            assert alert["severity"] == "very_low"

    def test_excess_nutrient_alert(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts

        # Log meal with excessive iron (upper limit is 45mg)
        log_meal_with_nutrition(
            meal_type="lunch",
            description="high iron meal",
            items=[{"food_name": "iron supplements"}],
            nutrition={
                "calories": 500,
                "protein": 20,
                "carbs": 60,
                "fat": 15,
                "fiber": 25,
                "iron": 60,        # 133% of upper limit (45mg)
                "vitamin_b12": 3,
                "vitamin_d": 15,
                "folate": 400,
                "zinc": 11,
                "magnesium": 400,
                "calcium": 1000,
                "potassium": 2600,
                "omega_3": 1.6,
                "vitamin_a": 900,
                "vitamin_c": 90,
            },
        )

        alerts = get_nutrition_alerts(days=3)

        # Should have an excess alert for iron
        excess_alerts = [a for a in alerts if a["type"] == "excess"]
        assert len(excess_alerts) == 1
        assert excess_alerts[0]["nutrient"] == "iron"
        assert excess_alerts[0]["severity"] == "high"  # 133% is < 150%
        assert excess_alerts[0]["upper_limit"] == 45

    def test_very_high_excess_alert(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts

        # Log meal with very excessive vitamin A (upper limit is 3000μg)
        log_meal_with_nutrition(
            meal_type="lunch",
            description="liver overdose",
            items=[{"food_name": "liver"}],
            nutrition={
                "calories": 500,
                "protein": 30,
                "carbs": 10,
                "fat": 20,
                "fiber": 25,
                "iron": 8,
                "vitamin_b12": 50,
                "vitamin_d": 15,
                "folate": 400,
                "zinc": 11,
                "magnesium": 400,
                "calcium": 1000,
                "potassium": 2600,
                "omega_3": 1.6,
                "vitamin_a": 5000,  # 167% of upper limit (3000μg)
                "vitamin_c": 90,
            },
        )

        alerts = get_nutrition_alerts(days=3)

        excess_alerts = [a for a in alerts if a["type"] == "excess" and a["nutrient"] == "vitamin_a"]
        assert len(excess_alerts) == 1
        assert excess_alerts[0]["severity"] == "very_high"  # 167% is >= 150%

    def test_excess_alerts_sorted_first(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts

        # Log meal with both deficiency and excess
        log_meal_with_nutrition(
            meal_type="lunch",
            description="mixed meal",
            items=[{"food_name": "food"}],
            nutrition={
                "calories": 500,
                "protein": 20,
                "carbs": 60,
                "fat": 15,
                "fiber": 5,        # 20% - deficiency
                "iron": 50,        # excess (limit 45mg)
                "vitamin_b12": 3,
                "vitamin_d": 15,
                "folate": 400,
                "zinc": 11,
                "magnesium": 400,
                "calcium": 1000,
                "potassium": 2600,
                "omega_3": 1.6,
                "vitamin_a": 900,
                "vitamin_c": 90,
            },
        )

        alerts = get_nutrition_alerts(days=3)

        # Excess alerts should come first (more urgent)
        assert len(alerts) > 0
        assert alerts[0]["type"] == "excess"

    def test_multiple_deficiency_alerts_sorted(self):
        from gutagent.db.models import log_meal_with_nutrition, get_nutrition_alerts
        
        # Log meal with multiple low nutrients
        log_meal_with_nutrition(
            meal_type="lunch",
            description="deficient meal",
            items=[{"food_name": "food"}],
            nutrition={
                "calories": 500,
                "protein": 20,
                "carbs": 60,
                "fat": 15,
                "fiber": 10,       # 40% (very_low)
                "iron": 4,         # 50% (low)
                "vitamin_c": 20,   # 22% (very_low)
            },
        )
        
        alerts = get_nutrition_alerts(days=3)
        deficiency_alerts = [a for a in alerts if a["type"] == "deficiency"]

        # Should be sorted by percent_of_rda ascending
        assert len(deficiency_alerts) >= 3
        assert deficiency_alerts[0]["percent_of_rda"] <= deficiency_alerts[1]["percent_of_rda"]


class TestToolHandlers:
    """Test tool handlers integrate correctly."""
    
    def test_log_meal_handler_with_items(self):
        from gutagent.tools.registry import execute_tool
        import json
        
        result = json.loads(execute_tool("log_meal", {
            "meal_type": "breakfast",
            "description": "eggs and toast",
            "items": [
                {"name": "eggs", "quantity": 2, "calories": 140, "protein": 12, "carbs": 1, "fat": 10},
                {"name": "toast", "quantity": 2, "calories": 160, "protein": 6, "carbs": 28, "fat": 2},
            ],
        }))
        
        assert result["status"] == "logged"
        assert result["items_count"] == 2
        assert result["nutrition"]["calories"] == 300
        assert result["nutrition"]["protein"] == 18
    
    def test_log_meal_handler_with_recipe(self):
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import save_recipe
        import json
        
        # Save a recipe first
        save_recipe("Test Dal", [
            {"name": "dal", "calories": 200, "protein": 12, "carbs": 35, "fat": 1},
            {"name": "ghee", "calories": 120, "protein": 0, "carbs": 0, "fat": 14},
        ])
        
        # Log meal using recipe
        result = json.loads(execute_tool("log_meal", {
            "description": "test dal",
            "recipe_name": "Test Dal",
            "items": [],  # Empty, will use recipe
        }))
        
        assert result["status"] == "logged"
        assert result["nutrition"]["calories"] == 320
    
    def test_save_recipe_handler(self):
        from gutagent.tools.registry import execute_tool
        import json
        
        result = json.loads(execute_tool("save_recipe", {
            "name": "Quick Salad",
            "ingredients": [
                {"name": "lettuce", "quantity": 100, "unit": "g", "calories": 15, "protein": 1, "carbs": 3, "fat": 0},
                {"name": "tomato", "quantity": 1, "unit": "piece", "calories": 20, "protein": 1, "carbs": 4, "fat": 0},
            ],
        }))
        
        assert result["status"] == "created"
        assert result["ingredients_count"] == 2
    
    def test_get_nutrition_summary_handler(self):
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_meal_with_nutrition
        import json
        
        log_meal_with_nutrition(
            meal_type="lunch",
            description="test",
            items=[{"food_name": "food"}],
            nutrition={"calories": 500, "protein": 25, "carbs": 50, "fat": 20, "fiber": 10},
        )
        
        result = json.loads(execute_tool("get_nutrition_summary", {"days": 3}))
        
        assert result["days_with_data"] == 1
        assert result["totals"]["calories"] == 500
    
    def test_get_nutrition_alerts_handler(self):
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import log_meal_with_nutrition
        import json
        
        # Log meal with no vitamin C
        log_meal_with_nutrition(
            meal_type="lunch",
            description="no vitamin c",
            items=[{"food_name": "food"}],
            nutrition={"calories": 500, "protein": 25, "carbs": 50, "fat": 20, "fiber": 25, "vitamin_c": 0},
        )
        
        result = json.loads(execute_tool("get_nutrition_alerts", {"days": 3}))
        
        assert result["count"] > 0
        nutrients_with_alerts = [a["nutrient"] for a in result["alerts"]]
        assert "vitamin_c" in nutrients_with_alerts
    
    def test_list_recipes_handler(self):
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import save_recipe
        import json
        
        save_recipe("Recipe 1", [{"name": "x", "calories": 10, "protein": 1, "carbs": 1, "fat": 0}])
        save_recipe("Recipe 2", [{"name": "y", "calories": 20, "protein": 2, "carbs": 2, "fat": 0}])
        
        result = json.loads(execute_tool("list_recipes", {}))
        
        assert result["count"] == 2
    
    def test_delete_recipe_handler(self):
        from gutagent.tools.registry import execute_tool
        from gutagent.db.models import save_recipe, get_recipe
        import json
        
        save_recipe("To Remove", [{"name": "x", "calories": 10, "protein": 1, "carbs": 1, "fat": 0}])
        
        result = json.loads(execute_tool("delete_recipe", {"name": "To Remove"}))
        
        assert result["status"] == "deleted"
        assert get_recipe("To Remove") is None
