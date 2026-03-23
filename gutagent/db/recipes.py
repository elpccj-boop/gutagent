"""Recipe storage and retrieval operations."""

import json
from datetime import datetime
from .connection import get_connection
from .common import round_nutrition


def save_recipe(name: str, ingredients: list[dict], notes: str | None = None,
                nutrition: dict | None = None, servings: float = 1) -> dict:
    """
    Save or update a recipe with pre-calculated per-serving nutrition.

    If nutrition is provided from ingredients totals, it will be divided by servings
    to get per-serving values.
    """
    conn = get_connection()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Calculate nutrition from ingredients if not provided
    if nutrition is None:
        nutrition = {
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0,
            "vitamin_b12": 0, "vitamin_d": 0, "folate": 0, "iron": 0, "zinc": 0,
            "magnesium": 0, "calcium": 0, "potassium": 0, "omega_3": 0,
            "vitamin_a": 0, "vitamin_c": 0
        }
        for item in ingredients:
            for key in nutrition:
                nutrition[key] += item.get(key, 0)

    # Divide by servings to get per-serving nutrition
    per_serving = {k: v / servings for k, v in nutrition.items()}

    # Round per-serving values before storing
    per_serving = round_nutrition(per_serving)

    # Check if recipe exists (case-insensitive)
    existing = conn.execute(
        "SELECT id FROM recipes WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE recipes SET ingredients = ?, notes = ?, servings = ?,
               calories = ?, protein = ?, carbs = ?, fat = ?, fiber = ?,
               vitamin_b12 = ?, vitamin_d = ?, folate = ?, iron = ?, zinc = ?,
               magnesium = ?, calcium = ?, potassium = ?, omega_3 = ?,
               vitamin_a = ?, vitamin_c = ?
               WHERE id = ?""",
            (json.dumps(ingredients), notes, servings,
             per_serving.get("calories", 0), per_serving.get("protein", 0),
             per_serving.get("carbs", 0), per_serving.get("fat", 0), per_serving.get("fiber", 0),
             per_serving.get("vitamin_b12", 0), per_serving.get("vitamin_d", 0),
             per_serving.get("folate", 0), per_serving.get("iron", 0), per_serving.get("zinc", 0),
             per_serving.get("magnesium", 0), per_serving.get("calcium", 0),
             per_serving.get("potassium", 0), per_serving.get("omega_3", 0),
             per_serving.get("vitamin_a", 0), per_serving.get("vitamin_c", 0),
             existing["id"])
        )
        recipe_id = existing["id"]
        action = "updated"
    else:
        cursor = conn.execute(
            """INSERT INTO recipes 
               (name, ingredients, notes, created_at, servings,
                calories, protein, carbs, fat, fiber,
                vitamin_b12, vitamin_d, folate, iron, zinc,
                magnesium, calcium, potassium, omega_3, vitamin_a, vitamin_c)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, json.dumps(ingredients), notes, timestamp, servings,
             per_serving.get("calories", 0), per_serving.get("protein", 0),
             per_serving.get("carbs", 0), per_serving.get("fat", 0), per_serving.get("fiber", 0),
             per_serving.get("vitamin_b12", 0), per_serving.get("vitamin_d", 0),
             per_serving.get("folate", 0), per_serving.get("iron", 0), per_serving.get("zinc", 0),
             per_serving.get("magnesium", 0), per_serving.get("calcium", 0),
             per_serving.get("potassium", 0), per_serving.get("omega_3", 0),
             per_serving.get("vitamin_a", 0), per_serving.get("vitamin_c", 0))
        )
        recipe_id = cursor.lastrowid
        action = "created"

    conn.commit()
    conn.close()

    return {
        "id": recipe_id, "status": action, "name": name, "servings": servings,
        "per_serving": {"calories": per_serving.get("calories", 0),
                        "protein": per_serving.get("protein", 0),
                        "fat": per_serving.get("fat", 0),
                        "carbs": per_serving.get("carbs", 0),
                        "fiber": per_serving.get("fiber", 0)}
    }


def get_recipe(name: str) -> dict | None:
    """Get a recipe by name (case-insensitive), including per-serving nutrition."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM recipes WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    conn.close()

    if row:
        return {
            "id": row["id"],
            "name": row["name"],
            "ingredients": json.loads(row["ingredients"]),
            "notes": row["notes"],
            "created_at": row["created_at"],
            "servings": row["servings"] or 1,
            "nutrition": {
                "calories": row["calories"] or 0,
                "protein": row["protein"] or 0,
                "carbs": row["carbs"] or 0,
                "fat": row["fat"] or 0,
                "fiber": row["fiber"] or 0,
                "vitamin_b12": row["vitamin_b12"] or 0,
                "vitamin_d": row["vitamin_d"] or 0,
                "folate": row["folate"] or 0,
                "iron": row["iron"] or 0,
                "zinc": row["zinc"] or 0,
                "magnesium": row["magnesium"] or 0,
                "calcium": row["calcium"] or 0,
                "potassium": row["potassium"] or 0,
                "omega_3": row["omega_3"] or 0,
                "vitamin_a": row["vitamin_a"] or 0,
                "vitamin_c": row["vitamin_c"] or 0,
            }
        }
    return None


def list_recipes() -> list[dict]:
    """List all saved recipes with per-serving nutrition."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, notes, created_at, servings,
               calories, protein, carbs, fat, fiber,
               vitamin_b12, vitamin_d, folate, iron, zinc, magnesium,
               calcium, potassium, omega_3, vitamin_a, vitamin_c
        FROM recipes ORDER BY name
    """).fetchall()
    conn.close()

    recipes = []
    for r in rows:
        recipes.append({
            "id": r["id"],
            "name": r["name"],
            "notes": r["notes"],
            "created_at": r["created_at"],
            "servings": r["servings"] or 1,
            "nutrition": {
                "calories": r["calories"] or 0,
                "protein": r["protein"] or 0,
                "carbs": r["carbs"] or 0,
                "fat": r["fat"] or 0,
                "fiber": r["fiber"] or 0,
                "vitamin_b12": r["vitamin_b12"] or 0,
                "vitamin_d": r["vitamin_d"] or 0,
                "folate": r["folate"] or 0,
                "iron": r["iron"] or 0,
                "zinc": r["zinc"] or 0,
                "magnesium": r["magnesium"] or 0,
                "calcium": r["calcium"] or 0,
                "potassium": r["potassium"] or 0,
                "omega_3": r["omega_3"] or 0,
                "vitamin_a": r["vitamin_a"] or 0,
                "vitamin_c": r["vitamin_c"] or 0,
            }
        })
    return recipes


def delete_recipe(name: str) -> dict:
    """Delete a recipe by name."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM recipes WHERE name = ? COLLATE NOCASE", (name,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return {"status": "deleted" if deleted else "not_found", "name": name}
