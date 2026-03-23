"""Database connection and initialization."""

import sqlite3
from datetime import datetime

from gutagent.paths import get_db_path, DB_PATH


def get_connection():
    """Get a database connection, creating the DB if needed."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP,
            meal_type TEXT,
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TIMESTAMP,
            symptom TEXT NOT NULL,
            severity INTEGER CHECK(severity BETWEEN 1 AND 10),
            timing TEXT,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TIMESTAMP,
            dose TEXT,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS vitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vital_type TEXT NOT NULL,
            systolic INTEGER,
            diastolic INTEGER,
            heart_rate INTEGER,
            value REAL,
            unit TEXT,
            occurred_at TIMESTAMP,
            notes TEXT
        );
            
        CREATE TABLE IF NOT EXISTS labs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_date TEXT NOT NULL,
            test_name TEXT NOT NULL,
            value REAL,
            unit TEXT,
            reference_range TEXT,
            status TEXT,
            notes TEXT,
            logged_at TIMESTAMP
        );
            
        CREATE TABLE IF NOT EXISTS sleep (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hours REAL,
            quality TEXT,
            occurred_at TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS exercise (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT NOT NULL,
            duration_minutes INTEGER,
            occurred_at TIMESTAMP,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            logged_at TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            ingredients JSON NOT NULL,
            notes TEXT,
            created_at TIMESTAMP,
            servings REAL DEFAULT 1,
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            fiber REAL DEFAULT 0,
            vitamin_b12 REAL DEFAULT 0,
            vitamin_d REAL DEFAULT 0,
            folate REAL DEFAULT 0,
            iron REAL DEFAULT 0,
            zinc REAL DEFAULT 0,
            magnesium REAL DEFAULT 0,
            calcium REAL DEFAULT 0,
            potassium REAL DEFAULT 0,
            omega_3 REAL DEFAULT 0,
            vitamin_a REAL DEFAULT 0,
            vitamin_c REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS meal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            quantity REAL,
            unit TEXT,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS meal_nutrition (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER NOT NULL UNIQUE,
            calories REAL DEFAULT 0,
            protein REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            fat REAL DEFAULT 0,
            fiber REAL DEFAULT 0,
            vitamin_b12 REAL DEFAULT 0,
            vitamin_d REAL DEFAULT 0,
            folate REAL DEFAULT 0,
            iron REAL DEFAULT 0,
            zinc REAL DEFAULT 0,
            magnesium REAL DEFAULT 0,
            calcium REAL DEFAULT 0,
            potassium REAL DEFAULT 0,
            omega_3 REAL DEFAULT 0,
            vitamin_a REAL DEFAULT 0,
            vitamin_c REAL DEFAULT 0,
            FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_meal_items_meal ON meal_items(meal_id);
        CREATE INDEX IF NOT EXISTS idx_meal_nutrition_meal ON meal_nutrition(meal_id);
    """)
    conn.commit()
    conn.close()


def validate_timestamp(occurred_at: str | None) -> str:
    """Validate and return a timestamp string. Raises ValueError for invalid dates."""
    if occurred_at is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    datetime.fromisoformat(occurred_at)
    return occurred_at
