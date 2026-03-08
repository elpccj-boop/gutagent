# GutAgent — Personalized Dietary AI Agent
## Architecture & Build Guide (Updated March 2026)

---

## What It Does

An AI agent that:
1. **Knows your medical profile** — IBD, triggers, medications, labs, family history, preferences
2. **Has tools** — meal logging, symptom tracking, vitals, sleep, exercise, medications, journal, profile updates
3. **Interprets your data** — Claude reviews your timeline to identify patterns and correlations
4. **Pulls dynamic context** — system prompt combines static profile with recent data from all tables
5. **Converses naturally** — "I had eggs and mutton for lunch" or "slept about 5 hours, pretty restless"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    CLI Interface                    │
│              (rich + prompt_toolkit)                │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Agent Loop (agent.py)              │
│                                                     │
│  1. User message + conversation history             │
│  2. System prompt built from:                       │
│     - Static profile (profile.json)                 │
│     - Dynamic context (recent data from all tables) │
│  3. Claude decides: respond OR call tool(s)         │
│  4. If tool → execute → feed result back → loop     │
│  5. Repeat until Claude produces final response     │
│                                                     │
│  (Core agentic loop — no framework, just while loop │
│   with Claude API + tool dispatch)                  │
└──────────┬──────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────┐
     │  Tool Registry             │
     │  (tools/registry.py)       │
     │                            │
     │  • log_meal                │
     │  • log_symptom             │
     │  • log_vital               │
     │  • log_medication_event    │
     │  • log_sleep               │
     │  • log_exercise            │
     │  • log_journal             │
     │  • query_logs              │
     │  • get_profile             │
     │  • correct_log             │
     │  • update_profile          │
     └─────┬──────────────────────┘
           │
           ▼
     ┌────────────────────────────┐
     │  SQLite Database           │
     │  (data/gutagent.db)        │
     │                            │
     │  • meals                   │
     │  • symptoms                │
     │  • vitals                  │
     │  • medication_events       │
     │  • labs                    │
     │  • sleep                   │
     │  • exercise                │
     │  • journal                 │
     └────────────────────────────┘
```

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.13 | Best AI ecosystem |
| LLM | Claude API (claude-sonnet-4-5) | Reasoning, function calling, empathetic tone |
| Database | SQLite (WAL mode) | Zero setup, file-based, perfect for personal tools |
| CLI | `rich` + `prompt_toolkit` | Beautiful terminal UI |
| Profile | JSON file | Static medical data, injected into system prompt |

### Future additions (not yet built)
| Component | Choice | Purpose |
|-----------|--------|---------|
| Vector DB | ChromaDB | RAG over IBD dietary research (Phase 4) |
| Nutrition API | USDA FoodData Central | Calorie/macro/micro lookup (Phase 5) |
| Web UI | FastAPI + HTMX or Streamlit | When CLI isn't enough (Phase 6) |

---

## Project Structure

```
gutagent_project/
├── .gitignore
├── data/
│   ├── gutagent.db               # SQLite database (all dynamic data)
│   ├── profile.json              # Static medical profile (gitignored)
│   └── profile_template.json     # Empty template for new users
├── gutagent/
│   ├── __init__.py
│   ├── main.py                   # Entry point — CLI chat loop
│   ├── agent.py                  # Core agent loop (LLM + tool dispatch)
│   ├── config.py                 # Tool definitions, model config
│   ├── profile.py                # Profile loading/saving
│   ├── tools/
│   │   ├── __init__.py
│   │   └── registry.py           # All tool handlers + dispatch
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py             # All DB operations (schema + CRUD)
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── system.py             # System prompt builder (static + dynamic)
│   ├── rag/                      # Empty — Phase 4
│   └── utils/
│       ├── check_data.py         # Query DB with filters and args
│       └── import_labs.py        # Bulk import lab results
└── README.md
```

### .gitignore
```
data/gutagent.db
data/profile.json
.env
__pycache__/
*.pyc
```

### Design decisions

**Consolidated tool handlers** — All handlers in `registry.py`, all DB ops in `models.py`. Each handler is 5-10 lines. Split into separate files only when a module exceeds ~300 lines.

**Profile vs Database** — Static facts (conditions, family history, dietary rules) live in `profile.json`. Dynamic data (meals, symptoms, vitals, sleep, exercise, etc.) lives in the database. System prompt pulls from both sources every API call.

**Dynamic context includes everything** — At session start, Claude sees recent data from all tables (meals, symptoms, vitals, sleep, exercise, meds, labs, journal). This eliminates redundant queries. `query_logs` is for searching further back or filtering.

**Claude interprets, code fetches** — No complex analysis code. Tools fetch data, Claude interprets patterns. This works better than coded correlation engines.

**No ORM** — Direct SQLite with `sqlite3.Row` for dict-like access. Simpler, fewer dependencies, good enough for a personal tool.

---

## Dynamic Context

The system prompt includes recent data from all tables, loaded at session start via `get_dynamic_context()`:

| Data | Time Window | Notes |
|------|-------------|-------|
| Medication timeline | All history | Full timeline for context |
| Latest labs | Most recent test date | Flagged abnormals |
| Vitals | Last 7 days | BP, weight, etc. |
| Meals | Last 3 days | More frequent, shorter window |
| Symptoms | Last 7 days | With severity |
| Sleep | Last 7 days | Hours and quality |
| Exercise | Last 7 days | Activity and duration |
| Journal | Last 7 days | Freeform notes |

Claude always has this context without needing to query. Tools are for deeper searches or longer time ranges.

---

## Database Schema

### meals
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| occurred_at | TIMESTAMP | When meal was eaten (inferred by Claude from context) |
| meal_type | TEXT | breakfast, lunch, dinner, snack |
| description | TEXT | Natural language description |
| foods | JSON | Extracted individual foods as array |
| notes | TEXT | Additional context |

### symptoms
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| occurred_at | TIMESTAMP | When symptom occurred |
| symptom | TEXT | bloating, fatigue, anxiety, brain_fog, etc. |
| severity | INTEGER | 1-10, always asked — never guessed |
| timing | TEXT | Relative to meals or time of day |
| notes | TEXT | Additional context |

### vitals
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| vital_type | TEXT | blood_pressure, weight, temperature, etc. |
| systolic | INTEGER | BP top number |
| diastolic | INTEGER | BP bottom number |
| heart_rate | INTEGER | Often measured with BP |
| value | REAL | For non-BP vitals (weight, temp, etc.) |
| unit | TEXT | lbs, kg, F, C, %, etc. |
| occurred_at | TIMESTAMP | When reading was taken |
| logged_at | TIMESTAMP | When entered into database |
| notes | TEXT | Position, context, reading number |

### medication_events
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| medication | TEXT | Name of medication (or full med list for snapshots) |
| event_type | TEXT | started, stopped, dose_changed, side_effect, snapshot |
| occurred_at | TIMESTAMP | When event happened |
| logged_at | TIMESTAMP | When entered into database |
| dose | TEXT | Dose information |
| notes | TEXT | Additional context |

`snapshot` event type stores medication state at a point in time (e.g., doctor visits). The full medication timeline is dumped into the system prompt — Claude interprets the history rather than code trying to parse it.

### labs
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| test_date | TEXT | When test was performed (YYYY-MM format) |
| test_name | TEXT | Name of test |
| value | REAL | Numeric result (NULL for non-numeric) |
| unit | TEXT | Unit of measurement |
| reference_range | TEXT | Normal range |
| status | TEXT | normal, high, low, critical, abnormal |
| notes | TEXT | Clinical significance |
| logged_at | TIMESTAMP | When imported |

### sleep
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| hours | REAL | Hours of sleep |
| quality | TEXT | good, poor, interrupted, restless, etc. |
| occurred_at | TIMESTAMP | The night of sleep |
| logged_at | TIMESTAMP | When entered |
| notes | TEXT | Additional context |

### exercise
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| activity | TEXT | walk, hike, gym, yoga, etc. |
| duration_minutes | INTEGER | Duration in minutes |
| occurred_at | TIMESTAMP | When exercise happened |
| logged_at | TIMESTAMP | When entered |
| notes | TEXT | Intensity, location, etc. |

### journal
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| description | TEXT | Freeform entry |
| occurred_at | TIMESTAMP | When it happened |
| logged_at | TIMESTAMP | When entered |

---

## Tools

| Tool | Purpose                                                           |
|------|-------------------------------------------------------------------|
| `log_meal` | Log what user ate — extracts foods, infers meal type and time     |
| `log_symptom` | Log physical/mental symptoms with severity                        |
| `log_vital` | Log BP, weight, temperature, etc.                                 |
| `log_medication_event` | Track medication starts, stops, dose changes                      |
| `log_sleep` | Log sleep hours and quality                                       |
| `log_exercise` | Log physical activity                                             |
| `log_journal` | Freeform notes and life events                                    |
| `query_logs` | Search across all tables — for deeper dives or longer time ranges |
| `get_profile` | Retrieve full medical profile                                     |
| `correct_log` | Update or delete existing entries                                 |
| `update_profile` | Add/modify profile data (conditions, suggestions, etc.)           |

### query_logs types

| Query Type | What it returns | Default days_back |
|------------|-----------------|-------------------|
| `recent_meals` | Meals with foods | 7 |
| `recent_symptoms` | Symptoms with severity | 7 |
| `food_search` | Meals containing specific food | all |
| `symptom_search` | Specific symptom history | all |
| `date_range` | Meals + symptoms together | 7 |
| `recent_vitals` | Vitals (BP, weight, etc.) | 0 (all data) |
| `recent_meds` | Medication events | 365 |
| `recent_labs` | Lab results | latest test date |
| `recent_sleep` | Sleep entries | 7 |
| `recent_exercise` | Exercise entries | 7 |
| `recent_journal` | Journal entries | 7 |

### correct_log actions

| Action | What it does | Required |
|--------|-------------|----------|
| `update` | Change fields on an existing entry | table, entry_id, updates dict |
| `delete` | Remove an entry | table, entry_id |

Allowed tables: meals, symptoms, vitals, medication_events, sleep, exercise, journal.

### update_profile actions

| Action | What it does |
|--------|-------------|
| `append` | Add to a list (e.g., conditions.other) |
| `set` | Replace a value |
| `remove` | Remove item from a list (matches by substring) |

---

## Profile Structure (profile.json)

The profile stores static facts. Dynamic data lives in the database.

```json
{
  "personal": {
    "sex": "",
    "dob": "YYYY-MM-DD",
    "notes": ""
  },
  "conditions": {
    "primary": "",
    "chronic": [],
    "other": [],
    "ruled_out": [],
    "procedures": []
  },
  "lifestyle": {
    "notes": ""
  },
  "medications": {
    "notes": ""
  },
  "dietary": {
    "triggers": [],
    "safe_foods": [],
    "notes": ""
  },
  "family_history": {
    "notes": ""
  },
  "clinical_context": {
    "notes": ""
  },
  "suggestions": {
    "tests_to_request": [],
    "to_discuss_with_doctor": [],
    "other": []
  },
  "upcoming_appointments": {}
}
```

Users expand this structure as needed. The template is minimal; individual profiles can have detailed nested structures.

---

## Agent Loop (agent.py)

```python
while iteration < max_iterations:
    response = client.messages.create(
        model=MODEL,
        system=system_prompt,    # Static profile + dynamic context
        tools=TOOLS,
        messages=messages,       # Full conversation history
        max_tokens=4096
    )
    
    if response.stop_reason == "tool_use":
        # Extract tool calls from response
        # Execute each via registry.execute_tool()
        # Append tool_use and tool_result to messages
        # Loop again — Claude sees results and decides next action
    else:
        # Extract text response, display to user, done
```

Key points:
- Stateless API — full conversation history sent every call
- Claude can call multiple tools in a single response
- Message flow: user → assistant(tool_use) → user(tool_result) → assistant(text)
- Max iterations prevent infinite loops

---

## Data Flow Examples

### "I had eggs and mutton with ghee for lunch"
1. User message → agent loop
2. Claude calls `log_meal(meal_type="lunch", description="eggs and mutton with ghee", foods=["eggs", "mutton", "ghee"])`
3. Registry dispatches to `models.log_meal()` → INSERT into meals table
4. Result returned to Claude → "Logged your lunch: eggs, mutton, ghee."

### "I'm feeling bloated"
1. Claude asks severity first (prompt rule — never guess)
2. User says "about a 5"
3. Claude calls `log_symptom(symptom="bloating", severity=5)`
4. Claude already has recent meals in dynamic context, notes potential triggers

### "Slept about 5 hours, pretty restless"
1. Claude calls `log_sleep(hours=5, quality="restless")`
2. Logged and confirmed

### "Went for a 20 minute walk"
1. Claude calls `log_exercise(activity="walk", duration_minutes=20)`
2. Logged and confirmed

### "How am I doing?"
1. Claude already has recent data in dynamic context
2. Claude reviews meals, symptoms, sleep, exercise, vitals
3. Responds with patterns and observations — no tool calls needed

### "Do you see patterns in my symptoms over the last month?"
1. Claude calls `query_logs` for longer time range (beyond dynamic context)
2. Reviews the data and identifies correlations

### "Remember that I have hypohidrosis"
1. Claude calls `update_profile(section="conditions.chronic", action="append", value="Hypohidrosis (lifelong reduced sweating, poor heat tolerance)")`
2. Profile updated, persists across sessions

### "Save that test suggestion"
1. Claude calls `update_profile(section="suggestions.tests_to_request", action="append", value="B12 levels — fatigue and neurological symptoms")`
2. Saved for future doctor visits

---

## Utility Scripts (utils/)

```bash
# Check specific tables
python -m gutagent.utils.check_data meals              # just meals
python -m gutagent.utils.check_data symptoms vitals    # symptoms and vitals
python -m gutagent.utils.check_data labs --status critical  # abnormal labs only
python -m gutagent.utils.check_data vitals --days 7    # last 7 days

# Bulk import (one-time, per user)
python -m gutagent.utils.import_labs    # lab results from reports
```

---

## Build Progress

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Done | Python fundamentals, environment setup |
| Phase 1 | ✅ Done | Core agent loop, tool calling, CLI |
| Phase 2 | ✅ Done | Meal/symptom logging, vitals, medications, labs, corrections, unified queries |
| Phase 3 | ✅ Done | Pattern interpretation, profile updates, sleep/exercise/journal tracking |
| Phase 4 | 🔲 Planned | RAG knowledge base with IBD research |
| Phase 5 | 🔲 Planned | USDA nutrition API |
| Phase 6 | 🔲 Planned | Web UI |

---

## Making It Shareable

The codebase separates generic from personal:

**Generic (same for everyone):**
- Agent loop, tool calling, message handling
- Database schema
- All tool definitions and handlers
- System prompt structure
- Utility scripts (check_data.py)
- `profile_template.json`

**Personal (different per user):**
- `profile.json` (each user fills in their own)
- Import scripts (one-time, per user's historical data)
- `gutagent.db` (each user's data)

To share: a new user copies `profile_template.json` to `profile.json`, fills in their details, and starts logging.

---

## Next Steps

1. **Accumulate data** — continue daily logging
2. **Phase 4: RAG** — ChromaDB with IBD dietary research for evidence-grounded advice
3. **Phase 5: Nutrition API** — USDA FoodData Central for real nutritional data
4. **Phase 6: Web/Mobile UI** — PWA or FastAPI + HTMX for phone access
5. **Setup wizard** — guided first-run for new users
