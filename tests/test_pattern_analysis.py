"""Tests for food-symptom pattern analysis."""

import json
import sqlite3
import os
import tempfile
from datetime import datetime, timedelta
from unittest import mock

import pytest

# Patch DB_PATH before importing models so all operations use the test database
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)

with mock.patch.dict("os.environ"):
    import gutagent.db.models as models
    models.DB_PATH = _test_db_path


@pytest.fixture(autouse=True)
def fresh_db():
    """Reset the database before each test."""
    models.DB_PATH = _test_db_path
    conn = sqlite3.connect(_test_db_path)
    conn.executescript("""
        DROP TABLE IF EXISTS meals;
        DROP TABLE IF EXISTS symptoms;
        DROP TABLE IF EXISTS correlations;
        DROP TABLE IF EXISTS medication_events;
        DROP TABLE IF EXISTS vitals;
        DROP TABLE IF EXISTS labs;
    """)
    conn.close()
    models.init_db()
    yield
    # Clean up after each test
    conn = sqlite3.connect(_test_db_path)
    conn.executescript("""
        DROP TABLE IF EXISTS meals;
        DROP TABLE IF EXISTS symptoms;
        DROP TABLE IF EXISTS correlations;
        DROP TABLE IF EXISTS medication_events;
        DROP TABLE IF EXISTS vitals;
        DROP TABLE IF EXISTS labs;
    """)
    conn.close()


def _log_meal(description, foods, hours_ago=0, meal_type="lunch"):
    """Helper to log a meal at a specific time in the past."""
    occurred_at = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    return models.log_meal(
        meal_type=meal_type,
        description=description,
        foods=foods,
        occurred_at=occurred_at,
    )


def _log_symptom(symptom, severity, hours_ago=0):
    """Helper to log a symptom at a specific time in the past."""
    occurred_at = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
    return models.log_symptom(
        symptom=symptom,
        severity=severity,
        occurred_at=occurred_at,
    )


class TestInsufficientData:
    def test_no_meals(self):
        _log_symptom("bloating", 5, hours_ago=1)
        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "insufficient_data"

    def test_no_symptoms(self):
        _log_meal("rice and chicken", ["rice", "chicken"], hours_ago=2)
        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "insufficient_data"

    def test_empty_database(self):
        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "insufficient_data"
        assert result["meals_count"] == 0
        assert result["symptoms_count"] == 0


class TestBasicCorrelation:
    def test_symptom_after_meal_is_detected(self):
        """A symptom 2 hours after a meal should produce a correlation."""
        _log_meal("spicy curry", ["curry", "rice"], hours_ago=3)
        _log_symptom("bloating", 6, hours_ago=1)

        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "ok"
        assert len(result["correlations"]) > 0

        foods_found = {c["food"].lower() for c in result["correlations"]}
        assert "curry" in foods_found
        assert "rice" in foods_found

    def test_symptom_too_early_is_ignored(self):
        """A symptom less than 0.5 hours after a meal should not correlate."""
        _log_meal("salad", ["lettuce", "tomato"], hours_ago=2)
        _log_symptom("nausea", 4, hours_ago=1.8)  # only 0.2 hours after meal

        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "ok"
        assert len(result["correlations"]) == 0

    def test_symptom_too_late_is_ignored(self):
        """A symptom more than 8 hours after a meal should not correlate."""
        _log_meal("breakfast", ["eggs", "toast"], hours_ago=12)
        _log_symptom("bloating", 5, hours_ago=2)  # 10 hours after meal

        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "ok"
        assert len(result["correlations"]) == 0

    def test_symptom_before_meal_is_ignored(self):
        """A symptom before a meal should not correlate."""
        _log_meal("lunch", ["chicken"], hours_ago=1)
        _log_symptom("pain", 7, hours_ago=3)  # 2 hours BEFORE the meal

        result = models.analyze_food_symptom_patterns(days_back=7)
        assert result["status"] == "ok"
        assert len(result["correlations"]) == 0


class TestSymptomRate:
    def test_high_symptom_rate_scores_higher(self):
        """A food that causes symptoms 3/4 times should rank above one that causes 3/10."""
        # "dairy" eaten 4 times, 3 with symptoms
        for i in range(4):
            _log_meal(f"dairy meal {i}", ["dairy"], hours_ago=48 + i * 24)
        for i in range(3):
            _log_symptom("bloating", 5, hours_ago=48 + i * 24 - 2)  # 2 hours after each meal

        # "bread" eaten 10 times, 3 with symptoms
        for i in range(10):
            _log_meal(f"bread meal {i}", ["bread"], hours_ago=48 + i * 24 + 0.5)
        for i in range(3):
            _log_symptom("bloating", 5, hours_ago=48 + i * 24 + 0.5 - 2)

        result = models.analyze_food_symptom_patterns(days_back=60)
        assert result["status"] == "ok"

        # Find the dairy and bread correlations
        dairy_corr = next((c for c in result["correlations"] if c["food"].lower() == "dairy"), None)
        bread_corr = next((c for c in result["correlations"] if c["food"].lower() == "bread"), None)

        assert dairy_corr is not None
        assert bread_corr is not None
        assert dairy_corr["symptom_rate"] > bread_corr["symptom_rate"]
        # Dairy should rank higher (higher score)
        assert dairy_corr["score"] > bread_corr["score"]

    def test_symptom_rate_calculation(self):
        """Verify symptom_rate = occurrences / times_eaten."""
        # Eat chicken 4 times, get symptoms after 2 of them
        for i in range(4):
            _log_meal(f"chicken meal {i}", ["chicken"], hours_ago=24 + i * 24)
        _log_symptom("pain", 5, hours_ago=24 - 2)
        _log_symptom("pain", 5, hours_ago=48 - 2)

        result = models.analyze_food_symptom_patterns(days_back=30)
        chicken_corr = next(c for c in result["correlations"] if c["food"].lower() == "chicken")

        assert chicken_corr["occurrences"] == 2
        assert chicken_corr["times_eaten"] == 4
        assert chicken_corr["symptom_rate"] == 0.5


class TestConfidence:
    def test_low_confidence_few_meals(self):
        """Fewer than 3 total meals with the food -> low confidence."""
        _log_meal("test meal", ["garlic"], hours_ago=3)
        _log_symptom("bloating", 7, hours_ago=1)

        result = models.analyze_food_symptom_patterns(days_back=7)
        garlic = next(c for c in result["correlations"] if c["food"].lower() == "garlic")
        assert garlic["confidence"] == "low"

    def test_high_confidence(self):
        """3+ occurrences with 50%+ symptom rate -> high confidence."""
        for i in range(4):
            _log_meal(f"garlic meal {i}", ["garlic"], hours_ago=24 + i * 24)
            _log_symptom("bloating", 6, hours_ago=24 + i * 24 - 2)

        result = models.analyze_food_symptom_patterns(days_back=30)
        garlic = next(c for c in result["correlations"] if c["food"].lower() == "garlic")
        assert garlic["confidence"] == "high"
        assert garlic["symptom_rate"] == 1.0


class TestCoOccurrence:
    def test_always_eaten_together_flagged(self):
        """Foods that always appear in the same meal should have always_eaten_with."""
        for i in range(3):
            _log_meal(f"combo meal {i}", ["chicken", "rice"], hours_ago=24 + i * 24)
            _log_symptom("bloating", 5, hours_ago=24 + i * 24 - 2)

        result = models.analyze_food_symptom_patterns(days_back=30)
        chicken_corr = next(c for c in result["correlations"] if c["food"].lower() == "chicken")
        rice_corr = next(c for c in result["correlations"] if c["food"].lower() == "rice")

        assert "always_eaten_with" in chicken_corr
        assert "rice" in chicken_corr["always_eaten_with"]
        assert "always_eaten_with" in rice_corr
        assert "chicken" in rice_corr["always_eaten_with"]

    def test_sometimes_separate_not_flagged(self):
        """Foods that sometimes appear separately should NOT have always_eaten_with."""
        # Two meals with chicken+rice, one meal with chicken alone
        _log_meal("combo 1", ["chicken", "rice"], hours_ago=72)
        _log_symptom("bloating", 5, hours_ago=70)
        _log_meal("combo 2", ["chicken", "rice"], hours_ago=48)
        _log_symptom("bloating", 5, hours_ago=46)
        _log_meal("solo chicken", ["chicken"], hours_ago=24)
        _log_symptom("bloating", 5, hours_ago=22)

        result = models.analyze_food_symptom_patterns(days_back=30)
        chicken_corr = next(c for c in result["correlations"] if c["food"].lower() == "chicken")
        assert "always_eaten_with" not in chicken_corr


class TestSafeFoods:
    def test_safe_foods_detected(self):
        """Foods eaten 3+ times with no symptoms should appear in safe_foods."""
        # Rice eaten 4 times, no symptoms ever
        for i in range(4):
            _log_meal(f"rice meal {i}", ["rice"], hours_ago=24 + i * 24)

        # Need at least one symptom so we don't get insufficient_data
        # Add a different food with a symptom
        _log_meal("spicy meal", ["chili"], hours_ago=5)
        _log_symptom("pain", 7, hours_ago=3)

        result = models.analyze_food_symptom_patterns(days_back=30)
        safe_food_names = [f["food"] for f in result["safe_foods"]]
        assert "rice" in safe_food_names

    def test_food_with_symptoms_not_safe(self):
        """Foods that triggered symptoms should NOT appear in safe_foods."""
        for i in range(4):
            _log_meal(f"dairy meal {i}", ["dairy"], hours_ago=24 + i * 24)
            _log_symptom("bloating", 5, hours_ago=24 + i * 24 - 2)

        result = models.analyze_food_symptom_patterns(days_back=30)
        safe_food_names = [f["food"] for f in result["safe_foods"]]
        assert "dairy" not in safe_food_names

    def test_infrequent_food_not_safe(self):
        """Foods eaten fewer than 3 times shouldn't appear in safe_foods even without symptoms."""
        _log_meal("quinoa once", ["quinoa"], hours_ago=24)
        _log_meal("quinoa twice", ["quinoa"], hours_ago=48)
        # Need some data to avoid insufficient_data
        _log_meal("chili", ["chili"], hours_ago=5)
        _log_symptom("pain", 5, hours_ago=3)

        result = models.analyze_food_symptom_patterns(days_back=30)
        safe_food_names = [f["food"] for f in result["safe_foods"]]
        assert "quinoa" not in safe_food_names


class TestFilters:
    def test_symptom_focus(self):
        """symptom_focus should only return correlations for that symptom."""
        _log_meal("test meal", ["eggs"], hours_ago=5)
        _log_symptom("bloating", 5, hours_ago=3)
        _log_symptom("pain", 7, hours_ago=3)

        result = models.analyze_food_symptom_patterns(days_back=7, symptom_focus="bloating")
        symptoms_found = {c["symptom"] for c in result["correlations"]}
        assert "bloating" in symptoms_found
        assert "pain" not in symptoms_found

    def test_food_focus(self):
        """food_focus should only return correlations for that food."""
        _log_meal("mixed meal", ["eggs", "toast", "butter"], hours_ago=5)
        _log_symptom("bloating", 5, hours_ago=3)

        result = models.analyze_food_symptom_patterns(days_back=7, food_focus="eggs")
        foods_found = {c["food"].lower() for c in result["correlations"]}
        assert "eggs" in foods_found
        assert "toast" not in foods_found

    def test_days_back_filter(self):
        """Old data outside days_back should be excluded."""
        _log_meal("old meal", ["gluten"], hours_ago=24 * 40)  # 40 days ago
        _log_symptom("bloating", 5, hours_ago=24 * 40 - 2)

        _log_meal("recent meal", ["dairy"], hours_ago=5)
        _log_symptom("bloating", 5, hours_ago=3)

        result = models.analyze_food_symptom_patterns(days_back=7)
        foods_found = {c["food"].lower() for c in result["correlations"]}
        assert "dairy" in foods_found
        assert "gluten" not in foods_found


class TestDateValidation:
    def test_invalid_date_feb_29_non_leap_year(self):
        """Feb 29 in a non-leap year should be rejected."""
        with pytest.raises(ValueError):
            models.log_symptom("fatigue", 5, occurred_at="2026-02-29 14:00:00")

    def test_invalid_date_feb_30(self):
        """Feb 30 never exists."""
        with pytest.raises(ValueError):
            models.log_meal("lunch", "test", ["rice"], occurred_at="2026-02-30 12:00:00")

    def test_invalid_date_month_13(self):
        with pytest.raises(ValueError):
            models.log_vital("weight", occurred_at="2026-13-01 10:00:00", value=70, unit="kg")

    def test_invalid_date_rejected_for_medication(self):
        with pytest.raises(ValueError):
            models.log_medication_event("Aspirin", "started", occurred_at="2026-04-31 08:00:00")

    def test_valid_date_accepted(self):
        result = models.log_symptom("bloating", 5, occurred_at="2026-03-01 14:00:00")
        assert result["status"] == "logged"
        assert result["when"] == "2026-03-01 14:00:00"

    def test_feb_29_leap_year_accepted(self):
        result = models.log_meal("lunch", "rice", ["rice"], occurred_at="2028-02-29 12:00:00")
        assert result["status"] == "logged"

    def test_none_defaults_to_now(self):
        result = models.log_symptom("nausea", 3, occurred_at=None)
        assert result["status"] == "logged"
        # Should be a valid parseable timestamp close to now
        logged_time = datetime.fromisoformat(result["when"])
        assert abs((datetime.now() - logged_time).total_seconds()) < 5

    def test_invalid_date_does_not_insert(self):
        """An invalid date should not leave a row in the database."""
        with pytest.raises(ValueError):
            models.log_symptom("fatigue", 5, occurred_at="2026-02-29 14:00:00")
        conn = models.get_connection()
        count = conn.execute("SELECT COUNT(*) FROM symptoms").fetchone()[0]
        conn.close()
        assert count == 0


class TestOutputStructure:
    def test_result_fields(self):
        """Verify all expected fields are present in correlation results."""
        _log_meal("test", ["chicken"], hours_ago=5)
        _log_symptom("bloating", 5, hours_ago=3)

        result = models.analyze_food_symptom_patterns(days_back=7)
        assert "correlations" in result
        assert "safe_foods" in result
        assert "meals_count" in result
        assert "symptoms_count" in result
        assert "days_analyzed" in result

        corr = result["correlations"][0]
        expected_fields = {
            "food", "symptom", "occurrences", "times_eaten",
            "times_no_symptom", "symptom_rate", "avg_severity",
            "avg_hours_after", "confidence", "score", "instances",
        }
        assert expected_fields.issubset(corr.keys())

    def test_results_sorted_by_score(self):
        """Correlations should be sorted by score descending."""
        # High severity food
        for i in range(3):
            _log_meal(f"spicy {i}", ["chili"], hours_ago=24 + i * 24)
            _log_symptom("pain", 9, hours_ago=24 + i * 24 - 2)

        # Low severity food
        for i in range(3):
            _log_meal(f"mild {i}", ["lettuce"], hours_ago=24 + i * 24 + 0.5)
            _log_symptom("bloating", 2, hours_ago=24 + i * 24 + 0.5 - 2)

        result = models.analyze_food_symptom_patterns(days_back=30)
        scores = [c["score"] for c in result["correlations"]]
        assert scores == sorted(scores, reverse=True)

    def test_max_10_correlations(self):
        """Should return at most 10 correlations."""
        for i in range(15):
            _log_meal(f"food {i}", [f"food_{i}"], hours_ago=24 + i * 24)
            _log_symptom("bloating", 5, hours_ago=24 + i * 24 - 2)

        result = models.analyze_food_symptom_patterns(days_back=60)
        assert len(result["correlations"]) <= 10
