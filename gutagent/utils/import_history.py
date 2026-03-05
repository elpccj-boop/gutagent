"""
Import historical vitals and medication data into GutAgent database.

Run from the gutagent_project root:
    python import_history.py

This script parses doctor visit records and imports:
- Blood pressure, pulse, weight, temperature, O2 saturation into vitals table
- Medication snapshots into medication_events table
"""

import sqlite3
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "../..", "data", "gutagent.db")

RECORDS = [
    {
        "date": "2026-02-24",
        "meds": "wellbutrin 300, armodafinil 250",
        "bp": [(151, 88), (136, 87)],
        "pulse": 90,
        "weight_lbs": 125,
        "o2": 100,
        "temp_f": 98.2,
    },
    {
        "date": "2025-04-16",
        "meds": "wellbutrin 300, armodafinil 250",
    },
    {
        "date": "2025-01-15",
        "meds": "wellbutrin 300, armodafinil 200",
        "bp": [(131, 82)],
        "pulse": 88,
        "weight_lbs": 136.4,
        "o2": 98,
        "temp_f": 97.8,
    },
    {
        "date": "2024-11-25",
        "meds": "wellbutrin 300, armodafinil 200",
        "bp": [(121, 80)],
        "pulse": 82,
        "weight_lbs": 138,
        "o2": 98,
        "temp_f": 98.2,
    },
    {
        "date": "2024-08-30",
        "meds": "wellbutrin 300, armodafinil 200",
        "bp": [(112, 74)],
        "pulse": 90,
        "weight_lbs": 130,
        "o2": 97,
        "temp_f": 97.2,
    },
    {
        "date": "2023-07-10",
        "meds": "wellbutrin 300, armodafinil 150",
    },
    {
        "date": "2023-06-23",
        "meds": "wellbutrin 300, armodafinil 150, stopped phentermine 37.5",
        "bp": [(132, 84)],
        "pulse": 90,
        "weight_lbs": 130,
        "o2": 98,
        "temp_f": 98.0,
    },
    {
        "date": "2022-06-01",
        "meds": "wellbutrin 300, phentermine 37.5",
        "weight_lbs": 130,
    },
    {
        "date": "2021-11-30",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(115, 73)],
        "pulse": 98,
        "weight_lbs": 138,
        "o2": 99,
        "temp_f": 97.4,
    },
    {
        "date": "2020-10-20",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(122, 82)],
        "pulse": 93,
        "weight_lbs": 137,
        "o2": 98,
        "temp_f": 98.1,
    },
    {
        "date": "2019-12-16",
        "meds": "wellbutrin 300, phendimetrazine 105 (restarted 10/14/2019)",
        "bp": [(134, 95)],
        "pulse": 76,
        "weight_lbs": 136,
        "o2": 99,
        "temp_f": 97.6,
    },
    {
        "date": "2019-06-25",
        "meds": "nothing",
        "bp": [(113, 78)],
        "pulse": 74,
        "weight_lbs": 137,
        "o2": 98,
        "temp_f": 98.0,
    },
    {
        "date": "2019-02-22",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(130, 82)],
        "pulse": 81,
        "weight_lbs": 125,
        "temp_f": 98.2,
    },
    {
        "date": "2019-02-06",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(124, 85)],
        "pulse": 88,
        "weight_lbs": 127,
        "o2": 99,
        "temp_f": 97.6,
    },
    {
        "date": "2018-06-08",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(116, 75)],
        "pulse": 88,
        "weight_lbs": 121.6,
        "o2": 99,
    },
    {
        "date": "2018-04-10",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(114, 77)],
        "pulse": 102,
        "weight_lbs": 123,
        "o2": 99,
        "temp_f": 97.6,
    },
    {
        "date": "2017-06-06",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(120, 78)],
        "pulse": 76,
        "weight_lbs": 126,
        "temp_f": 98.6,
    },
    {
        "date": "2017-03-27",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(113, 71)],
        "pulse": 108,
        "weight_lbs": 129,
        "temp_f": 98.7,
    },
    {
        "date": "2017-03-23",
        "meds": "wellbutrin 300, phendimetrazine 105",
        "bp": [(113, 81)],
        "pulse": 85,
        "weight_lbs": 130,
    },
]


def import_data():
    conn = sqlite3.connect(DB_PATH)

    vitals_count = 0
    meds_count = 0

    for record in RECORDS:
        date = record["date"]
        timestamp = f"{date} 10:00:00"

        # Import blood pressure readings
        for i, (sys, dia) in enumerate(record.get("bp", [])):
            reading_num = i + 1
            notes = f"Doctor visit reading {reading_num}" if len(record.get("bp", [])) > 1 else "Doctor visit"
            conn.execute(
                """INSERT INTO vitals (vital_type, systolic, diastolic, heart_rate, occurred_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("blood_pressure", sys, dia, record.get("pulse"), timestamp, notes)
            )
            vitals_count += 1

        # Import weight
        if "weight_lbs" in record:
            conn.execute(
                """INSERT INTO vitals (vital_type, value, unit, occurred_at, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                ("weight", record["weight_lbs"], "lbs", timestamp, "Doctor visit")
            )
            vitals_count += 1

        # Import temperature
        if "temp_f" in record:
            conn.execute(
                """INSERT INTO vitals (vital_type, value, unit, occurred_at, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                ("temperature", record["temp_f"], "F", timestamp, "Doctor visit")
            )
            vitals_count += 1

        # Import O2 saturation
        if "o2" in record:
            conn.execute(
                """INSERT INTO vitals (vital_type, value, unit, occurred_at, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                ("oxygen_saturation", record["o2"], "%", timestamp, "Doctor visit")
            )
            vitals_count += 1

        # Import medication snapshot
        if record.get("meds") and record["meds"] != "nothing":
            conn.execute(
                """INSERT INTO medication_events (medication, event_type, occurred_at, notes)
                   VALUES (?, ?, ?, ?)""",
                (record["meds"], "snapshot", timestamp, "Doctor visit medications")
            )
            meds_count += 1
        elif record.get("meds") == "nothing":
            conn.execute(
                """INSERT INTO medication_events (medication, event_type, occurred_at, notes)
                   VALUES (?, ?, ?, ?)""",
                ("none", "snapshot", timestamp, "Doctor visit — no medications")
            )
            meds_count += 1

    conn.commit()
    conn.close()

    print(f"Imported {vitals_count} vital readings and {meds_count} medication snapshots.")
    print("Run check_data.py to verify.")


if __name__ == "__main__":
    import_data()