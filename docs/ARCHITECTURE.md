# GutAgent Architecture

Personal dietary AI agent for tracking food, symptoms, vitals, and health patterns.

## Overview

An AI agent that:
- Knows your medical profile (conditions, triggers, medications, preferences)
- Logs data conversationally (meals, symptoms, vitals, labs, sleep, exercise)
- Tracks nutrition with LLM-estimated macros and micronutrients
- Identifies patterns and correlations in your health data
- Available via CLI or mobile-friendly web UI

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interfaces                        │
│  ┌──────────────────┐         ┌──────────────────────────┐  │
│  │   CLI (run_cli)  │         │   Web UI (run_web)       │  │
│  │   rich + prompt  │         │   FastAPI + React PWA    │  │
│  └────────┬─────────┘         └────────────┬─────────────┘  │
│           └─────────────┬──────────────────┘                │
└─────────────────────────┼───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Loop (agent.py)                            │
│  • Builds system prompt (static profile + dynamic context)          │
│  • Sends to LLM with tool definitions                               │
│  • Executes tools, feeds results back until final response          │
│  • Tracks recent_logs for corrections, last_exchange for follow-ups │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │ LLM Provider│  │Tool Registry│  │  Database   │
   │   (llm/)    │  │  (tools/)   │  │   (db/)     │
   │ Claude/     │  │ 18 tools    │  │  SQLite     │
   │ Gemini/     │  │ log, query, │  │  10 tables  │
   │ OpenAI      │  │ correct,    │  │             │
   │             │  │ recipes,    │  │             │
   │             │  │ nutrition   │  │             │
   └─────────────┘  └─────────────┘  └─────────────┘
```

## Project Structure

```
gutagent/
├── run_cli.py              # CLI entry point
├── run_web.py              # Web server entry point
├── agent.py                # CLI agent loop
├── core.py                 # Shared logic (CLI + web)
├── config.py               # Tool definitions, model config
├── profile.py              # Profile loading/saving
├── paths.py                # Centralized path management
├── logging_config.py       # Logging setup
├── profile_template.json   # Template for new users
├── api/
│   └── server.py           # FastAPI + streaming
├── web/
│   ├── index.html          # Entry HTML
│   ├── app.jsx             # React chat UI
│   ├── sw.js               # Service worker (PWA)
│   └── manifest.json       # PWA manifest
├── llm/
│   ├── __init__.py         # get_provider() factory
│   ├── base.py             # BaseLLMProvider interface
│   ├── claude.py           # Claude provider
│   ├── gemini_provider.py  # Gemini provider
│   └── openai_provider.py  # OpenAI provider
├── tools/
│   └── registry.py         # Tool handlers + dispatch
├── db/
│   ├── __init__.py         # Re-exports all functions
│   ├── connection.py       # DB setup, schema
│   ├── common.py           # Shared utilities
│   ├── logs.py             # All logging operations
│   ├── recipes.py          # Recipe CRUD
│   └── nutrition.py        # RDA targets, alerts
├── prompts/
│   └── system.py           # System prompt builder
└── utils/
    └── check_data.py       # CLI data inspection utility

data/                       # User data (gitignored, create manually)
├── gutagent.db             # SQLite database (auto-created)
└── profile.json            # Copy from gutagent/profile_template.json

tests/
└── test_gutagent.py
```

## Tech Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Language | Python 3.13 | |
| LLM | Claude, Gemini, OpenAI | Provider abstraction in `llm/` |
| Database | SQLite (WAL mode) | Zero setup, file-based |
| CLI | rich + prompt_toolkit | Pretty terminal UI |
| Web Backend | FastAPI + SSE | Streaming responses |
| Web Frontend | React + Tailwind (CDN) | No build step, mobile-first |
| Auth | HTTP Basic Auth | Via `.env` credentials |

### LLM Providers

| Provider | Default | Smart | Cost (per 1M tokens) | Notes |
|----------|---------|-------|----------------------|-------|
| Claude | Haiku 4.5 | Sonnet 4.5 | $1/$5 — $3/$15 | Best tool calling, native streaming |
| Gemini | 2.5 Flash | 2.5 Pro | $0.30/$2.50 — $1.25/$10 | Free tier available, good quality |
| OpenAI | GPT-4o-mini | GPT-4o | $0.15/$0.60 — $2.50/$10 | Widely used, cheapest default tier |

*Cost format: input/output per million tokens*

Typical usage cost (~10K input, ~1K output / interaction):  
Claude Haiku: ~\$0.015, Gemini Flash: ~\$0.005, GPT-4o-mini: ~\$0.002.

Configure in `.env` (see Configuration section below).

### Streaming Support

All providers support true streaming in both CLI and Web UI:
- **Claude**: Native SSE streaming via `messages.stream()`
- **Gemini**: Native streaming via `generate_content_stream()`
- **OpenAI**: Native streaming via `stream=True`

### Prompt Caching

All providers implement prompt caching to reduce costs and latency:

| Provider | Cache Type | TTL | Discount |
|----------|-----------|-----|----------|
| Claude | Explicit (cache_control markers) | 5 min (default) or 1 hour | 90% read, +25% write |
| Gemini | Explicit (caches.create API) | 1 hour minimum | 90% (2.5+), 75% (2.0) |
| OpenAI | Automatic (prefix matching) | 5-10 min | 50% |

**What gets cached:**
- Static prompt (~5-6k tokens): System instructions, profile, tool definitions
- **Not cached**: Dynamic context (recent meals, vitals, alerts, conversation)

**Token usage is normalized** across all providers to match Claude's semantics:
- `input_tokens`: Uncached input only (dynamic context + user message)
- `cache_creation_input_tokens`: Tokens written to cache (first request)
- `cache_read_input_tokens`: Tokens read from cache (subsequent requests)
- `output_tokens`: Model's response

Total input = `input_tokens` + (`cache_creation_input_tokens` OR `cache_read_input_tokens`)

## Core Concepts

### Profile vs Database

**Profile** (`data/profile.json`) — Static facts that rarely change:
- Medical conditions, family history
- Dietary triggers and safe foods
- Lifestyle notes, clinical context
- Suggestions for tests to request

**Database** (`data/gutagent.db`) — Dynamic data logged over time:
- Meals with nutrition
- Symptoms with severity
- Vitals (BP, weight, etc.)
- Lab results
- Medications (start/stop/dose changes)
- Sleep, exercise, journal entries
- Saved recipes

### System Prompt Structure

The system prompt has two parts:

1. **Static** (cached) — Instructions + profile JSON
2. **Dynamic** (rebuilt each call) — Recent data from all tables + nutrition alerts + recently logged entries

This gives the LLM context without needing explicit queries for common questions like "what did I eat today?"

### Dynamic Context Data Windows

All data includes IDs for corrections (e.g., `[id:47]`).

| Data | Days | Notes |
|------|------|-------|
| Medications | 30 | Current + recent changes |
| Labs | Latest per test | Most recent value for each test type |
| Vitals | 3 | |
| Symptoms | 3 | |
| Meals | 3 | With nutrition breakdown |
| Sleep | 3 | |
| Exercise | 3 | |
| Journal | 3 | Max 5 entries |
| Recipes | All | Names only (backend fetches nutrition) |

#### query_logs Tool

Returns formatted summaries for analysis (token-efficient, no IDs).

| Query Type | Default | Notes |
|------------|---------|-------|
| `recent_meals` | 7 days | |
| `recent_symptoms` | 7 days | |
| `recent_sleep` | 7 days | |
| `recent_exercise` | 7 days | |
| `recent_journal` | 7 days | |
| `recent_vitals` | All | Returns summary with stats |
| `recent_meds` | All | Returns summary with current + history |
| `recent_labs` | Varies | Date (YYYY-MM-DD) or test name |

Recipes have separate tools (`list_recipes`, `get_recipe`, etc.).

#### Database Functions

| Data | Logging | List (for context) | Summary (for query_logs) | Search |
|------|---------|------------------|-------------------------|--------|
| Meals | `log_meal_with_nutrition` | `get_recent_meals` | — | `search_meals_by_food` |
| Symptoms | `log_symptom` | `get_recent_symptoms` | — | `search_symptoms` |
| Vitals | `log_vital` | `get_recent_vitals` | `get_vitals_summary` | — |
| Meds | `log_medication_event` | `get_current_and_recent_meds` | `get_meds_summary` | — |
| Labs | `log_lab` | `get_latest_labs_per_test` | — | `get_labs_by_date`, `search_labs_by_test` |
| Sleep | `log_sleep` | `get_recent_sleep` | — | — |
| Exercise | `log_exercise` | `get_recent_exercise` | — | — |
| Journal | `log_journal_entry` | `get_recent_journal` | — | — |

### Agent Loop

```
User message
    ↓
Build system prompt (static + dynamic)
    ↓
Send to LLM with tools
    ↓
┌─► LLM responds with tool_use?
│       ↓ yes
│   Execute tool via registry
│   Append result to messages
│   Loop again
│       ↓ no
└── Return text response
```

Key behaviors:
- No full conversation history (token-efficient)
- `recent_logs` enables "change that to 5" without IDs
- `last_exchange` enables follow-ups like "yes" or "that's right"
- Max 10 iterations per turn (safety valve)

### Nutrition Tracking

1. User mentions food → LLM estimates macros + 11 micronutrients
2. If food matches saved recipe → use stored per-serving nutrition
3. Tool handler sums nutrition, stores in `meal_nutrition` table
4. Alerts calculated on 3-day rolling average vs RDA targets

No external nutrition API — LLM knowledge handles diverse cuisines well.

## Database Schema

All timestamps are local time.

| Table | Key Fields |
|-------|------------|
| meals | occurred_at, meal_type, description |
| meal_items | meal_id, food_name, quantity, unit |
| meal_nutrition | meal_id, calories, protein, carbs, fat, fiber, + 11 micros |
| symptoms | occurred_at, symptom, severity (1-10), timing, notes |
| vitals | vital_type, systolic/diastolic (BP), value/unit (others) |
| labs | test_date, test_name, value, unit, status |
| medications | medication, event_type (started/stopped/dose_changed) |
| sleep | occurred_at, hours, quality |
| exercise | occurred_at, activity, duration_minutes |
| journal | logged_at, description |
| recipes | name, ingredients (JSON), servings, per-serving nutrition |

## Tools (18)

### Logging
| Tool | Purpose |
|------|---------|
| log_meal | Food with itemized nutrition |
| log_symptom | Physical/mental symptoms with severity |
| log_vital | BP, weight, temperature, etc. |
| log_lab | Lab test results |
| log_medication_event | Med starts, stops, dose changes |
| log_sleep | Sleep hours and quality |
| log_exercise | Physical activity |
| log_journal | Freeform notes |

### Query & Edit
| Tool | Purpose |
|------|---------|
| query_logs | Search across tables with filters |
| correct_log | Update or delete entries |
| get_profile | Get full medical profile |
| update_profile | Add/modify profile data |

### Recipes & Nutrition
| Tool | Purpose |
|------|---------|
| save_recipe | Save with per-serving nutrition |
| get_recipe | Retrieve recipe details |
| list_recipes | List all saved recipes |
| delete_recipe | Remove a recipe |
| get_nutrition_summary | Totals and daily averages |
| get_nutrition_alerts | Deficiency/excess alerts |

## Running

### CLI
```bash
python -m gutagent.run_cli
```

Commands: `--verbose`, `--quiet`, `--default`, `--smart`

### Web
```bash
python -m gutagent.run_web
```

Opens at `http://localhost:8000`. Mobile-friendly, installable as PWA.

### Remote Access

For phone access outside local network:
```bash
# Install cloudflared
brew install cloudflared  # or apt install cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

Set auth credentials in `.env`:
```bash
GUTAGENT_USERNAME=your_username
GUTAGENT_PASSWORD=your_password
```

## Configuration

### Environment Variables (`.env`)

Create a `.env` file in the project root (copy from `.env.example`):

```bash
# LLM Provider (pick one)
LLM_PROVIDER=claude          # claude, gemini, or openai

# API Keys (only need the one for your chosen provider)
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...

# Claude Cache TTL (optional)
# Default is 5 minutes. Set to "1h" for 1-hour cache (slightly higher cost)
# CLAUDE_CACHE_TTL=1h

# Web Authentication (optional, for remote access)
GUTAGENT_USERNAME=yourname
GUTAGENT_PASSWORD=yourpassword
```

### File Locations

| File | Purpose | Gitignored |
|------|---------|------------|
| `data/profile.json` | Your medical profile | ✅ |
| `data/gutagent.db` | Your health data | ✅ |
| `.env` | API keys and auth | ✅ |
| `gutagent/profile_template.json` | Template for new users | ❌ |
| `.env.example` | Template for env vars | ❌ |

Paths can be overridden via environment variables:
- `GUTAGENT_DATA_DIR` — Base data directory (default: `./data`)
- `GUTAGENT_DB_PATH` — Database file path
- `GUTAGENT_PROFILE_PATH` — Profile file path
- `GUTAGENT_LOG_LEVEL` — Logging level (DEBUG, INFO, WARNING, ERROR)

## Testing

```bash
# Run all tests
pytest tests/test_gutagent.py -v

# Run specific test class
pytest tests/test_gutagent.py::TestMeals -v

# Stop on first failure
pytest tests/test_gutagent.py -v -x
```

Tests use a temporary database and profile — your real data is never touched.

## Known Limitations

1. **No offline queue** — Web UI requires connectivity
2. **Session state in memory** — Web sessions lost on server restart
3. **Single user** — No multi-user support (personal tool)

## Future Considerations

When evolving to a proper mobile app:
- Current architecture separates concerns well for porting
- `agent.py` logic is interface-agnostic
- Database schema is stable, can migrate to any SQL backend
- Tool definitions in `config.py` can serialize to any format
- Profile structure is JSON, portable anywhere

The main work would be:
1. Native mobile UI (React Native, Flutter, or native)
2. Backend API deployment (current FastAPI works as-is)
3. User authentication system
4. Cloud database (Postgres, Supabase, etc.)
