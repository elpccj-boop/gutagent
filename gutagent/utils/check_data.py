"""Check GutAgent database contents.

Usage:
    python utils/check_data.py              # show all
    python utils/check_data.py meals        # just meals
    python utils/check_data.py symptoms vitals  # symptoms and vitals
    python utils/check_data.py labs --status abnormal  # filter labs by status
    python utils/check_data.py vitals --days 7  # last 7 days only
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "../..", "data", "gutagent.db")

SECTIONS = ["meals", "symptoms", "meds", "vitals", "labs"]

def parse_args():
    args = sys.argv[1:]
    sections = []
    status_filter = None
    days_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1]
            i += 2
        elif args[i] == "--days" and i + 1 < len(args):
            days_filter = int(args[i + 1])
            i += 2
        else:
            sections.append(args[i])
            i += 1

    if not sections:
        sections = SECTIONS

    return sections, status_filter, days_filter


def show_meals(conn, days_filter):
    print("\n--- Meals ---")
    query = "SELECT * FROM meals ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM meals WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        print(f"{row['id']}: {row['occurred_at']} | {row['meal_type']} | {row['description']} | {row['foods']}")


def show_symptoms(conn, days_filter):
    print("\n--- Symptoms ---")
    query = "SELECT * FROM symptoms ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM symptoms WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        print(f"{row['id']}: {row['occurred_at']} | {row['symptom']} | severity: {row['severity']} | {row['notes']}")


def show_meds(conn, days_filter):
    print("\n--- Medication Events ---")
    query = "SELECT * FROM medication_events ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM medication_events WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        print(f"{row['id']}: {row['occurred_at']} | {row['medication']} | {row['event_type']} | {row['dose']} | {row['notes']}")


def show_vitals(conn, days_filter):
    print("\n--- Vitals ---")
    query = "SELECT * FROM vitals ORDER BY occurred_at"
    if days_filter:
        cutoff = (datetime.now() - timedelta(days=days_filter)).strftime("%Y-%m-%d")
        query = f"SELECT * FROM vitals WHERE occurred_at >= '{cutoff}' ORDER BY occurred_at"
    for row in conn.execute(query):
        if row['vital_type'] == 'blood_pressure':
            print(f"{row['id']}: {row['occurred_at']} | BP: {row['systolic']}/{row['diastolic']} HR:{row['heart_rate']} | {row['notes']}")
        else:
            print(f"{row['id']}: {row['occurred_at']} | {row['vital_type']}: {row['value']} {row['unit']} | {row['notes']}")


def show_labs(conn, status_filter):
    print("\n--- Labs ---")
    query = "SELECT * FROM labs ORDER BY test_date, status"
    if status_filter:
        query = f"SELECT * FROM labs WHERE status = '{status_filter}' ORDER BY test_date, test_name"
    for row in conn.execute(query):
        val = f"{row['value']} {row['unit']}" if row['value'] else "—"
        ref = f"(ref: {row['reference_range']})" if row['reference_range'] else ""
        notes = f"| {row['notes']}" if row['notes'] else ""
        print(f"{row['test_date']} | {row['test_name']}: {val} {ref} [{row['status']}] {notes}")


def main():
    sections, status_filter, days_filter = parse_args()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    for section in sections:
        if section == "meals":
            show_meals(conn, days_filter)
        elif section == "symptoms":
            show_symptoms(conn, days_filter)
        elif section == "meds":
            show_meds(conn, days_filter)
        elif section == "vitals":
            show_vitals(conn, days_filter)
        elif section == "labs":
            show_labs(conn, status_filter)
        else:
            print(f"Unknown section: {section}. Options: {', '.join(SECTIONS)}")

    conn.close()


if __name__ == "__main__":
    main()