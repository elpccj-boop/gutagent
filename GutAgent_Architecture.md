# GutAgent — Personalized Dietary AI Agent
## Architecture & Build Guide (Updated March 2026)

---

## What It Does

An AI agent that:
1. **Knows your medical profile** — IBD, triggers, medications, labs, family history, preferences
2. **Has tools** — meal logging, symptom tracking, vitals, sleep, exercise, medications, journal, profile updates, recipes, nutrition tracking
3. **Interprets your data** — Claude reviews your timeline to identify patterns and correlations
4. **Pulls dynamic context** — system prompt combines static profile with recent data from all tables
5. **Tracks nutrition** — Claude estimates calories, protein, and 11 micronutrients for every meal
6. **Converses naturally** — "I had eggs and mutton for lunch" or "slept about 5 hours, pretty restless"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CLI Interface                        │
│              (rich + prompt_toolkit)                    │
│                                                         │
│  Commands: --haiku, --sonnet, --verbose, --quiet        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent Loop (agent.py)                  │
│                                                         │
│  1. User message + conversation history                 │
│  2. System prompt built from:                           │
│     - Static profile (profile.json)                     │
│     - Dynamic context (recent data from all tables)     │
│     - Nutrition alerts (3-day rolling)                  │
│  3. Claude decides: respond OR call tool(s)             │
│  4. If tool → execute → feed result back → loop         │
│  5. Repeat until Claude produces final response         │
│                                                         │
│  (Core agentic loop — no framework, just while loop     │
│   with Claude API + tool dispatch)                      │
└──────────┬──────────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────┐
     │  Tool Registry             │
     │  (tools/registry.py)       │
     │                            │
     │  Logging:                  │
     │  • log_meal with nutrition │
     │  • log_symptom             │
     │  • log_vital               │
     │  • log_medication_event    │
     │  • log_sleep               │
     │  • log_exercise            │
     │  • log_journal             │
     │                            │
     │  Query:                    │
     │  • query_logs              │
     │  • get_profile             │
     │                            │
     │  Edit:                     │
     │  • correct_log             │
     │  • update_profile          │
     │                            │
     │  Recipes:                  │
     │  • save_recipe             │
     │  • get_recipe              │
     │  • list_recipes            │
     │  • delete_recipe           │
     │                            │
     │  Nutrition:                │
     │  • get_nutrition_summary   │
     │  • get_nutrition_alerts    │
     └─────┬──────────────────────┘
           │
           ▼
     ┌────────────────────────────┐
     │  SQLite Database           │
     │  (data/gutagent.db)        │
     │                            │
     │  Core tables:              │
     │  • meals                   │
     │  • symptoms                │
     │  • vitals                  │
     │  • medication_events       │
     │  • labs                    │
     │  • sleep                   │
     │  • exercise                │
     │  • journal                 │
     │                            │
     │  Nutrition tables:         │
     │  • recipes                 │
     │  • meal_items              │
     │  • meal_nutrition          │
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
| Nutrition | Claude estimates | No external API — Claude knows food nutrition |

### Future additions (not yet built)
| Component | Choice | Purpose |
|-----------|--------|---------|
| Web UI | FastAPI + HTMX or Streamlit | When CLI isn't enough (Phase 6) |
| Vector DB | ChromaDB | RAG over IBD dietary research (Phase 7) |

---

## Project Structure

```
gutagent_project/
├── .gitignore
├── data/
│   ├── gutagent.db*              # SQLite database (all dynamic data)
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
│   │   └── system.py             # System prompt builder (static + dynamic + alerts)
│   ├── rag/                      # Empty — Phase 7
│   └── utils/
│       └── check_data.py         # Query DB with filters and args
├── tests/
└── README.md
```

### .gitignore
```
data/gutagent.db*
data/profile.json
reports/
.env
__pycache__/
*.pyc
```

### Design decisions

**Consolidated tool handlers** — All handlers in `registry.py`, all DB ops in `models.py`. Each handler is 5-10 lines. Split into separate files only when a module exceeds ~300 lines.

**Profile vs Database** — Static facts (conditions, family history, dietary rules) live in `profile.json`. Dynamic data (meals, symptoms, vitals, sleep, exercise, etc.) lives in the database. System prompt pulls from both sources every API call.

**Dynamic context includes everything** — At session start, Claude sees recent data from all tables (meals, symptoms, vitals, sleep, exercise, meds, labs, journal) plus nutrition alerts. This eliminates redundant queries. `query_logs` is for searching further back or filtering.

**Claude interprets, code fetches** — No complex analysis code. Tools fetch data, Claude interprets patterns. This works better than coded correlation engines.

**Claude estimates nutrition** — No external nutrition API. Claude directly estimates calories, protein, and micronutrients for any food (including regional cuisines like Indian). More reliable than API lookups for diverse foods.

**No ORM** — Direct SQLite with `sqlite3.Row` for dict-like access. Simpler, fewer dependencies, good enough for a personal tool.

**All timestamps local** — No UTC conversion. `occurred_at` is always local time (inferred by Claude from context or set to current time). Easier to read and reason about.

---

## CLI Commands

| Command | Effect |
|---------|--------|
| `--haiku` | Switch to Haiku model (cheaper, good for routine logging) |
| `--sonnet` | Switch to Sonnet model (default, better analysis) |
| `--verbose` | Show tool calls |
| `--quiet` | Hide tool calls (default) |
| `quit` / `exit` | End session |

---

## Dynamic Context

The system prompt includes recent data from all tables, loaded at session start via `get_dynamic_context()`:

| Data | Time Window | Notes |
|------|-------------|-------|
| Medication timeline | All history | Full timeline for context |
| Latest labs | Most recent test date | Flagged abnormals |
| Vitals | Last 7 days | BP, weight, etc. |
| Meals | Last 3 days | With nutrition if available |
| Symptoms | Last 7 days | With severity |
| Sleep | Last 7 days | Hours and quality |
| Exercise | Last 7 days | Activity and duration |
| Journal | Last 7 days | Freeform notes |
| Saved recipes | All | Recipe names listed |
| Nutrition alerts | 3-day rolling | Deficiencies (<70% RDA) and excesses (above safe limits) |

Claude always has this context without needing to query. Tools are for deeper searches or longer time ranges.

---

## Database Schema

All timestamps are **local time** (no UTC).

### meals
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| occurred_at | TIMESTAMP | When meal was eaten (inferred by Claude from context) |
| meal_type | TEXT | breakfast, lunch, dinner, snack |
| description | TEXT | Natural language description |
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
| notes | TEXT | Position, context, reading number |

### medication_events
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| medication | TEXT | Name of medication (or full med list for snapshots) |
| event_type | TEXT | started, stopped, dose_changed, side_effect, snapshot |
| occurred_at | TIMESTAMP | When event happened |
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
| status | TEXT | normal, low, high, critical, abnormal |
| notes | TEXT | Additional context |
| logged_at | TIMESTAMP | When entered into database |

### sleep
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| occurred_at | TIMESTAMP | Night of sleep (date user went to bed) |
| hours | REAL | Hours slept |
| quality | TEXT | good, poor, interrupted, restless, etc. |
| notes | TEXT | Additional context |

### exercise
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| occurred_at | TIMESTAMP | When exercise happened |
| activity | TEXT | walk, hike, gym, yoga, etc. |
| duration_minutes | INTEGER | Duration |
| notes | TEXT | Intensity, location, how it felt |

### journal
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| logged_at | TIMESTAMP | When entry was created |
| description | TEXT | Freeform content |

### recipes
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| name | TEXT | Recipe name (case-insensitive unique) |
| ingredients | JSON | Array of ingredients with nutrition |
| notes | TEXT | Recipe notes |
| created_at | TIMESTAMP | When recipe was saved |

### meal_items
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| meal_id | INTEGER | Foreign key to meals |
| food_name | TEXT | Individual food item |
| quantity | REAL | Amount |
| unit | TEXT | g, piece, cup, etc. |
| is_spice | BOOLEAN | True for spices (turmeric, cumin, etc.) |

### meal_nutrition
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| meal_id | INTEGER | Foreign key to meals (unique) |
| calories | REAL | Total calories |
| protein | REAL | Grams |
| carbs | REAL | Grams |
| fat | REAL | Grams |
| fiber | REAL | Grams |
| vitamin_b12 | REAL | μg |
| vitamin_d | REAL | μg |
| folate | REAL | μg |
| iron | REAL | mg |
| zinc | REAL | mg |
| magnesium | REAL | mg |
| calcium | REAL | mg |
| potassium | REAL | mg |
| omega_3 | REAL | g |
| vitamin_a | REAL | μg |
| vitamin_c | REAL | mg |

---

## Nutrition Tracking

### How It Works

1. User mentions a meal → Claude parses into individual food items
2. Claude estimates nutrition for each item using its knowledge (no external API)
3. Tool handler sums nutrition and stores in `meal_items` + `meal_nutrition`
4. Nutrition alerts calculated on 3-day rolling average

### Tracked Nutrients (17 total)

**Macros:** calories, protein, carbs, fat, fiber

**Micronutrients:** vitamin B12, vitamin D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, vitamin A, vitamin C

### Nutrition Alerts

Alerts are based on 3-day rolling daily averages.

**Deficiency alerts** (below RDA):
- **< 70% RDA** → "low" severity
- **< 50% RDA** → "very_low" severity

**Excess alerts** (above safe upper limit):
- **> 100% of upper limit** → "high" severity
- **> 150% of upper limit** → "very_high" severity

Alerts appear in:
- System prompt (Claude sees them proactively)
- `get_nutrition_alerts` tool (on-demand)

Excess alerts are sorted first (more urgent), then deficiencies by percent.

### RDA Targets

| Nutrient | Daily Target | Upper Limit | Unit |
|----------|--------------|-------------|------|
| Fiber | 25 | — | g |
| Vitamin B12 | 2.4 | — | μg |
| Vitamin D | 15 | 100 | μg |
| Folate | 400 | 1000 | μg |
| Iron | 8 | 45 | mg |
| Zinc | 11 | 40 | mg |
| Magnesium | 400 | — | mg |
| Calcium | 1000 | 2500 | mg |
| Potassium | 2600 | — | mg |
| Omega-3 | 1.6 | — | g |
| Vitamin A | 900 | 3000 | μg |
| Vitamin C | 90 | — | mg |

### Recipes

Saved recipes enable consistent nutrition tracking for repeated dishes:
- User describes ingredients → Claude saves with `save_recipe`
- When logging a meal, Claude checks for matching recipe
- Recipe ingredients include spice tracking (turmeric, cumin, etc.)

---

## Tools (17 total)

| Tool | What it does |
|------|--------------|
| `log_meal` | Log food with itemized nutrition estimates |
| `log_symptom` | Log physical/mental symptoms with severity |
| `log_vital` | Log BP, weight, temperature, etc. |
| `log_medication_event` | Track medication starts, stops, dose changes |
| `log_sleep` | Log sleep hours and quality |
| `log_exercise` | Log physical activity |
| `log_journal` | Freeform notes and life events |
| `query_logs` | Search across all tables — for deeper dives or longer time ranges |
| `get_profile` | Retrieve full medical profile |
| `correct_log` | Update or delete existing entries |
| `update_profile` | Add/modify profile data (conditions, suggestions, etc.) |
| `save_recipe` | Save a recipe with ingredients and nutrition |
| `get_recipe` | Retrieve a saved recipe |
| `list_recipes` | List all saved recipes |
| `delete_recipe` | Delete a saved recipe |
| `get_nutrition_summary` | Get nutrition totals and daily averages |
| `get_nutrition_alerts` | Get deficiency and excess alerts |

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
        model=model,              # Sonnet or Haiku
        system=system_prompt,     # Static profile + dynamic context + alerts
        tools=TOOLS,
        messages=messages,        # Full conversation history
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
- Model switchable at runtime via `--haiku` / `--sonnet`

---

## Data Flow Examples

### "I had eggs and mutton with ghee for lunch"
1. User message → agent loop
2. Claude calls `log_meal` with itemized nutrition:
   ```json
   {
     "meal_type": "lunch",
     "description": "eggs and mutton with ghee",
     "items": [
       {"name": "eggs", "quantity": 2, "calories": 140, "protein": 12, ...},
       {"name": "mutton", "quantity": 150, "unit": "g", "calories": 280, "protein": 25, ...},
       {"name": "ghee", "quantity": 1, "unit": "tbsp", "calories": 120, "fat": 14, ...}
     ]
   }
   ```
3. Registry sums nutrition, inserts into meals + meal_items + meal_nutrition
4. Result returned to Claude → "Logged your lunch: eggs and mutton with ghee (~540 cal, 37g protein)."

### "I'm feeling bloated"
1. Claude asks severity first (prompt rule — never guess)
2. User says "about a 5"
3. Claude calls `log_symptom(symptom="bloating", severity=5)`
4. Claude already has recent meals in dynamic context, notes potential triggers

### "How's my nutrition?"
1. Claude calls `get_nutrition_summary(days=3)`
2. Reviews totals and daily averages
3. Mentions any alerts (e.g., "You're low on vitamin C this week")

### "Remember that I have hypohidrosis"
1. Claude calls `update_profile(section="conditions.chronic", action="append", value="Hypohidrosis (lifelong reduced sweating, poor heat tolerance)")`
2. Profile updated, persists across sessions

### "Save that test suggestion"
1. Claude calls `update_profile(section="suggestions.tests_to_request", action="append", value="B12 levels — fatigue and neurological symptoms")`
2. Saved for future doctor visits

### "Save my dal tadka recipe"
1. User describes ingredients
2. Claude calls `save_recipe` with ingredients and nutrition estimates
3. Next time user logs "dal tadka", Claude uses `recipe_name` parameter

---

## Utility Scripts (utils/)

```bash
# Check specific tables
python -m gutagent.utils.check_data meals              # just meals
python -m gutagent.utils.check_data symptoms vitals    # symptoms and vitals
python -m gutagent.utils.check_data labs --status critical  # abnormal labs only
python -m gutagent.utils.check_data vitals --days 7    # last 7 days
```

---

## Build Progress

| Phase   | Status | Description |
|---------|--------|-------------|
| Phase 0 | ✅ Done | Python fundamentals, environment setup |
| Phase 1 | ✅ Done | Core agent loop, tool calling, CLI |
| Phase 2 | ✅ Done | Meal/symptom logging, vitals, medications, labs, corrections, unified queries |
| Phase 3 | ✅ Done | Pattern interpretation, profile updates, sleep/exercise/journal tracking |
| Phase 4 | ⏭️ Skipped | RAG knowledge base (deferred — Claude's knowledge + web search sufficient) |
| Phase 5 | ✅ Done | Nutrition tracking (Claude estimates, no external API) |
| Phase 6 | 🔲 Planned | Web UI |
| Phase 7 | 🔲 Planned | RAG for IBD research if needed |


---

## API Costs

Rough estimates with Sonnet:
- ~$0.02 per message exchange
- ~$0.20 per day (10 messages)
- ~$5 lasts about a month

Use `--haiku` for routine logging to reduce costs by ~10x.

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

1. **Accumulate data** — continue daily logging with nutrition tracking
2. **Phase 6: Web/Mobile UI** — PWA or FastAPI + HTMX for phone access
3. **Phase 7: RAG** — ChromaDB with IBD dietary research if Claude's knowledge proves insufficient
4. **Setup wizard** — guided first-run for new users
