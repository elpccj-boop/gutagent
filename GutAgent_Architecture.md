# GutAgent — Personalized Dietary AI Agent
## Architecture & Build Guide (Updated March 2026)

---

## What It Does

An AI agent that:
1. **Knows your medical profile** — IBD, triggers, medications, labs, family history, preferences
2. **Has tools** — meal logging, symptom tracking, vitals recording, medication event tracking, pattern analysis, data correction
3. **Learns from your data** — correlates foods with symptoms, tracks vitals trends over time
4. **Pulls dynamic context** — system prompt combines static profile with live database queries (full medication timeline, latest labs, recent vitals)
5. **Converses naturally** — "I had eggs and mutton for lunch" or "my BP this morning was 138/85 pulse 72"

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    CLI Interface                      │
│              (rich + prompt_toolkit)                  │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Agent Loop (agent.py)                │
│                                                      │
│  1. User message + conversation history              │
│  2. System prompt built from:                        │
│     - Static profile (profile.json)                  │
│     - Dynamic DB queries (meds, labs, vitals)        │
│  3. Claude decides: respond OR call tool(s)          │
│  4. If tool → execute → feed result back → loop      │
│  5. Repeat until Claude produces final response       │
│                                                      │
│  (Core agentic loop — no framework, just while loop  │
│   with Claude API + tool dispatch)                    │
└──────────┬──────────────────────────────────────────┘
           │
     ┌─────▼──────────────────────┐
     │  Tool Registry             │
     │  (tools/registry.py)       │
     │                            │
     │  • log_meal                │
     │  • log_symptom             │
     │  • log_medication_event    │
     │  • log_vital               │
     │  • query_journal           │
     │  • analyze_patterns        │
     │  • get_profile             │
     │  • correct_entry           │
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
     │  • correlations            │
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

## Project Structure (Actual)

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
│   ├── profile.py                # Profile loading from JSON
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
│       ├── fix_data.py           # One-off data corrections
│       ├── import_history.py     # Bulk import vitals + med snapshots
│       └── import_labs.py        # Bulk import lab results
└── scratch/                      # Practice scripts
```

### .gitignore
```
data/gutagent.db
data/profile.json
utils/import_history.py
utils/import_labs.py
.env
__pycache__/
*.pyc
```

### Design decisions

**Consolidated tool handlers** — All handlers in `registry.py`, all DB ops in `models.py`. Each handler is 5-10 lines. Split into separate files only when a module exceeds ~300 lines.

**Profile vs Database** — Static facts (conditions, family history, dietary rules) live in `profile.json`. Dynamic data (medications, vitals, labs, meals, symptoms) live in the database. System prompt pulls from both sources every API call.

**No ORM** — Direct SQLite with `sqlite3.Row` for dict-like access. Simpler, fewer dependencies, good enough for a personal tool.

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
| symptom | TEXT | bloating, fatigue, pain, brain_fog, etc. |
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
| logged_at | TIMESTAMP | When imported into database |

Labs are imported in bulk via scripts, not logged through the agent conversationally.

### correlations
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| food | TEXT | Trigger food |
| symptom | TEXT | Associated symptom |
| occurrences | INTEGER | Number of times observed |
| avg_severity | REAL | Average symptom severity |
| avg_hours_after | REAL | Typical delay |
| confidence | TEXT | low, medium, high |
| first_seen | TIMESTAMP | First observation |
| last_seen | TIMESTAMP | Most recent observation |
| notes | TEXT | Pattern details |

Not yet populated — Phase 3 pattern analysis computes correlations on the fly. Persisting strong correlations is a future enhancement.

---

## System Prompt Architecture

The system prompt is built dynamically on every API call by `prompts/system.py`:

```
┌─────────────────────────────────────────────────────┐
│  System Prompt                                       │
│                                                      │
│  1. Agent identity and behavior rules                │
│  2. Current date/time                                │
│  3. Static profile (from profile.json)               │
│  4. Dynamic context (from database):                 │
│     - Full medication timeline (all events +         │
│       snapshots, Claude interprets)                  │
│     - Latest lab results                             │
│     - Recent vitals (last 7 days)                    │
│  5. Core behavior rules:                             │
│     - Proactive logging (meals, symptoms,            │
│       vitals, medication events)                     │
│     - Never fabricate patient data (use general      │
│       medical knowledge freely, but never invent     │
│       facts about THIS patient)                      │
│     - Always ask severity — never guess              │
│     - Separate tool calls per concern                │
│     - Use correct_entry for corrections,             │
│       never create duplicates                        │
│     - Dietary guidance based on profile              │
│     - Pattern awareness                              │
└─────────────────────────────────────────────────────┘
```

### Key prompt rules
- **Never fabricate patient data** — only state what's in profile or database. General medical knowledge is fine for explaining conditions, suggesting questions for doctors, interpreting patterns, and providing dietary guidance.
- **Always ask severity** — never guess symptom severity.
- **Separate concerns** — if user mentions a meal AND a symptom, make separate tool calls.
- **Proactive logging** — log meals, symptoms, vitals, medication events without asking permission.
- **Corrections** — use `correct_entry` to update/delete, never create a new entry when fixing an old one.

---

## Tool Definitions

Eight tools defined in `config.py`:

| Tool | Purpose | Required params |
|------|---------|----------------|
| `log_meal` | Log food intake | description, foods |
| `log_symptom` | Log symptoms | symptom, severity |
| `log_medication_event` | Track med changes | medication, event_type |
| `log_vital` | Record BP, weight, etc. | vital_type |
| `query_journal` | Search all data: meals, symptoms, vitals, meds, labs | query_type |
| `analyze_patterns` | Find food-symptom correlations | (none required) |
| `get_profile` | Retrieve medical profile | (none required) |
| `correct_entry` | Update or delete existing entries | action, table, entry_id |

All logging tools include an `occurred_at` parameter for backdating entries. Claude infers timestamps from natural language ("yesterday lunch" → yesterday at 12:30).

### query_journal query types

| Query type | What it searches | Default days_back |
|------------|-----------------|-------------------|
| `recent_meals` | Meals table | 7 |
| `recent_symptoms` | Symptoms table | 7 |
| `food_search` | Meals by food name | all |
| `symptom_search` | Symptoms by type | all |
| `date_range` | Meals + symptoms together | 7 |
| `recent_vitals` | Vitals (BP, weight, temp, etc.) | 0 (all data) |
| `recent_meds` | Medication events | 365 |
| `recent_labs` | Lab results | latest test date |

### correct_entry actions

| Action | What it does | Required |
|--------|-------------|----------|
| `update` | Change fields on an existing entry | table, entry_id, updates dict |
| `delete` | Remove an entry | table, entry_id |

Allowed tables: meals, symptoms, vitals, medication_events.

---

## Profile Structure (profile.json — static only)

```json
{
  "personal": { "sex", "dob", "menopause_status" },
  "conditions": {
    "primary": "IBD diagnosis",
    "other": ["list of conditions"],
    "ruled_out": ["celiac (2018 biopsy)", "giardia", "granulomas", "dysplasia"],
    "procedures": ["mastectomy details", "colonoscopy details", "genetic testing status"]
  },
  "lifestyle": {
    "salt_intake": "",
    "weight": "",
    "activity": "",
    "stress": "",
    "sleep": ""
  },
  "medication_history": {
    "ssris_tried": "previous medications and outcomes",
    "stimulants": "timeline of stimulant medications"
  },
  "clinical_context": {
    "central_theory": "gut-brain axis hypothesis based on keto response",
    "breast_cancer_presentation": "clinical details"
  },
  "dietary": {
    "known_triggers": {
      "severe": ["confirmed severe reactions"],
      "general": ["category-level triggers"],
      "experimenting": ["foods being tested for tolerance"]
    },
    "safe_foods": [],
    "preferences": { "cooking_fat", "style", "avoids" },
    "history": { "keto_8_months", "implication" }
  },
  "family_history": {
    "cancer": "multi-generational history",
    "blood_pressure": "family BP history",
    "genetic_testing": "status and urgency",
    "treatment_warning": "relevant family treatment reactions"
  },
  "upcoming_appointments": {
    "elf_test": "date and purpose",
    "gastroenterologist": "date and doctor"
  }
}
```

Dynamic data (current medications, lab values, vitals) is NOT in the profile — it lives in the database and is pulled into the system prompt by `get_dynamic_context()`.

---

## Agent Loop (agent.py)

```python
while iteration < max_iterations:
    response = client.messages.create(
        model=MODEL,
        system=system_prompt,    # Static profile + dynamic DB context
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
3. Claude calls `log_symptom(symptom="bloating", severity=5)` AND `query_journal(query_type="recent_meals")`
4. Claude sees recent meals, notes any potential triggers, responds with observation

### "Actually change that severity to 4"
1. Claude calls `correct_entry(action="update", table="symptoms", entry_id=6, updates={"severity": 4})`
2. Existing entry updated — no duplicate created

### "How has my weight changed over the years?"
1. Claude calls `query_journal(query_type="recent_vitals", search_term="weight")`
2. Returns all weight readings (days_back defaults to 0 = all data)
3. Claude interprets the timeline narratively

### "Do you see any patterns in my symptoms?"
1. Claude calls `analyze_patterns(days_back=30)`
2. Engine finds food-symptom correlations within 0.5-8 hour windows
3. Results scored by frequency × severity, sorted by strength
4. Claude presents findings with clinical context from the profile

---

## Pattern Analysis Engine

Located in `models.py` as `analyze_food_symptom_patterns()`.

**How it works:**
1. Fetches all meals and symptoms within the time window
2. For each symptom, finds meals eaten 0.5-8 hours before
3. Pairs each food from those meals with the symptom
4. Counts occurrences, averages severity and time delay
5. Assigns confidence: low (<3 occurrences), medium (3-4), high (5+)
6. Returns top 10 correlations sorted by occurrences × average severity

**What it found with early data:**
- Every bloating episode followed grains or legumes
- Severity correlated with amount: mung + amaranth combo (7/10) vs single grain (4/10)
- Safe foods (chicken, mutton, banana, eggs) never appeared before symptom entries
- Armodafinil withdrawal symptoms (fatigue, body aches) correctly identified as separate from food triggers

---

## Utility Scripts (utils/)

```bash
# Check specific tables
python utils/check_data.py meals              # just meals
python utils/check_data.py symptoms vitals     # symptoms and vitals
python utils/check_data.py labs --status critical  # abnormal labs only
python utils/check_data.py vitals --days 7     # last 7 days

# Bulk import (one-time, per user — gitignored)
python utils/import_history.py    # historical vitals + med snapshots
python utils/import_labs.py       # lab results from reports
```

---

## Build Progress

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Done | Python fundamentals, environment setup |
| Phase 1 | ✅ Done | Core agent loop, tool calling, CLI |
| Phase 2 | ✅ Done | Meal/symptom logging, vitals, medications, labs, bulk import, corrections, unified queries |
| Phase 3 | ✅ Partial | Pattern analysis engine working, correlations computed on the fly. TODO: persist strong correlations, add medication-symptom correlation, time-of-day patterns |
| Phase 4 | 🔲 Planned | RAG knowledge base with IBD research |
| Phase 5 | 🔲 Planned | USDA nutrition API, recipe tools |
| Phase 6 | 🔲 Planned | Doctor report generator, web UI, conversation memory |

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

To share: a new user copies `profile_template.json` to `profile.json`, fills in their details, and starts logging. A first-run setup wizard (future feature) could walk them through it conversationally.

---

## Next Steps

1. **Accumulate data** — 2+ weeks of daily meal/symptom/BP logging for robust pattern analysis
2. **Doctor report generator** — export clean summary for April 8 appointment (BP trends, symptom patterns, medication timeline, food triggers, lab results)
3. **Persist correlations** — save strong patterns to correlations table
4. **Phase 4: RAG** — ChromaDB with IBD dietary research for evidence-grounded advice
5. **Phase 5: Nutrition API** — USDA FoodData Central for real nutritional data
6. **Phase 6: Web/Mobile UI** — PWA or FastAPI + HTMX for phone access
7. **Conversation memory** — persist key insights across sessions
8. **Setup wizard** — guided first-run for new users
