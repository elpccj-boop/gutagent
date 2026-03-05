"""
Import lab results into GutAgent database.

Run from the gutagent_project root:
    python import_labs.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../..", "data", "gutagent.db")

# February 2026 labs — from Vijaya Diagnostic Centre, Hyderabad
LABS_FEB_2026 = [
    # Abnormal results
    ("2026-02", "Fecal Calprotectin", 718, "ug/g", "< 50", "critical", "Confirms active intestinal inflammation"),
    ("2026-02", "Albumin/Creatinine Ratio (ACR)", 142.5, "mg/g", "< 30", "critical", "Microalbuminuria — early kidney stress, likely from high BP"),
    ("2026-02", "eGFR Cystatin C", 77, "ml/min", "> 90", "low", "G2 category — mild decrease in kidney filtration"),
    ("2026-02", "ESR", 51, "mm/hr", "0-30", "high", "Systemic inflammation marker, consistent with gut inflammation"),
    ("2026-02", "Total Cholesterol", 237, "mg/dL", "< 200", "high", "Borderline high"),
    ("2026-02", "LDL Cholesterol", 165, "mg/dL", "< 100", "high", "High — combined with BP increases cardiovascular risk"),
    ("2026-02", "Globulin", 4.5, "gm/dL", "1.8-3.6", "high", "Suggests chronic inflammation or immune activation"),
    ("2026-02", "Hemoglobin", 11.1, "gm/dL", "12.0-15.0", "low", "Mild anemia — history of iron deficiency"),
    ("2026-02", "Urine RBC", 5, "/HPF", "0-2", "high", "Mildly elevated — may indicate kidney or urinary tract involvement"),

    # Normal results
    ("2026-02", "Fasting Glucose", 78, "mg/dL", "< 100", "normal", None),
    ("2026-02", "HbA1c", 4.8, "%", "< 5.7", "normal", "Well within non-diabetic range"),
    ("2026-02", "TSH", 1.113, "uIU/mL", "0.4-4.0", "normal", None),
    ("2026-02", "Free T4", 1.12, "ng/dL", "0.8-1.8", "normal", None),
    ("2026-02", "CEA", 2.46, "ng/mL", "< 5", "normal", "No colorectal cancer signal"),
    ("2026-02", "CA-125", 10.1, "U/mL", "< 35", "normal", "No ovarian cancer signal"),
    ("2026-02", "CA 15.3", 22.11, "U/mL", "< 31.3", "normal", "No breast cancer recurrence signal"),
    ("2026-02", "CRP", 3.6, "mg/L", "< 5", "normal", None),
    ("2026-02", "IgE", 312.4, "IU/mL", "< 378", "normal", "No major allergic process"),
    ("2026-02", "Triglycerides", 58, "mg/dL", "< 150", "normal", "Excellent — good fat metabolism"),
    ("2026-02", "HDL Cholesterol", 60, "mg/dL", "> 50", "normal", "Desirable level"),
    ("2026-02", "SGPT (ALT)", None, "U/L", None, "normal", "Liver enzymes all normal"),
    ("2026-02", "SGOT (AST)", None, "U/L", None, "normal", "Liver enzymes all normal"),
    ("2026-02", "ALP", None, "U/L", None, "normal", None),
    ("2026-02", "GGT", None, "U/L", None, "normal", None),
    ("2026-02", "eGFR Creatinine", 100.7, "ml/min", "> 90", "normal", "Creatinine-based eGFR normal, but Cystatin C more sensitive"),

    # Imaging results (stored as labs for simplicity)
    ("2026-02", "Echo - Ejection Fraction", 68, "%", "> 55", "normal", "Normal chambers, good function"),
    ("2026-02", "Echo - Diastolic Function", None, None, None, "abnormal", "Grade I LV diastolic dysfunction"),
    ("2026-02", "Echo - Aortic Valve", None, None, None, "abnormal", "Sclerotic but opening well"),
    ("2026-02", "ECG", 73, "bpm", None, "normal", "Normal sinus rhythm"),
    ("2026-02", "Ultrasound - Liver", None, None, None, "abnormal", "Grade I fatty liver"),
    ("2026-02", "Ultrasound - Gallbladder", None, None, None, "abnormal", "Not visualized, echogenic foci suggest possible gallstones"),
    ("2026-02", "Ultrasound - Fibroid", None, "mm", None, "abnormal", "65 x 61 mm uterine fibroid"),
    ("2026-02", "Ultrasound - Kidneys", None, None, None, "normal", "Normal kidneys"),
]


def import_labs():
    conn = sqlite3.connect(DB_PATH)
    count = 0

    for test_date, test_name, value, unit, ref_range, status, notes in LABS_FEB_2026:
        conn.execute(
            """INSERT INTO labs (test_date, test_name, value, unit, reference_range, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (test_date, test_name, value, unit, ref_range, status, notes)
        )
        count += 1

    conn.commit()
    conn.close()
    print(f"Imported {count} lab results.")
    print("Run check_data.py to verify.")


if __name__ == "__main__":
    import_labs()