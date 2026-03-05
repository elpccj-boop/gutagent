import sqlite3
import json
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "gutagent.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("--- Meals ---")
for row in conn.execute("SELECT * FROM meals"):
    print(f"{row['id']}: {row['logged_at']} | {row['meal_type']} | {row['description']} | {json.loads(row['foods'])}")

print("\n--- Symptoms ---")
for row in conn.execute("SELECT * FROM symptoms"):
    print(f"{row['id']}: {row['logged_at']} | {row['symptom']} | severity: {row['severity']} | {row['notes']}")

conn.close()