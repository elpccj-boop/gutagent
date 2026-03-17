# GutAgent — Personalized Dietary AI Agent
## Architecture & Build Guide (Updated March 2026)

---

## What It Does

An AI agent that:
1. **Knows your medical profile** — IBD, triggers, medications, labs, family history, preferences
2. **Has tools** — meal logging, symptom tracking, vitals, sleep, exercise, medications, journal, profile updates, recipes, nutrition tracking
3. **Interprets your data** — LLM reviews your timeline to identify patterns and correlations
4. **Pulls dynamic context** — system prompt combines static profile with recent data from all tables
5. **Tracks nutrition** — LLM estimates calories, protein, and 11 micronutrients for every meal
6. **Converses naturally** — "I had eggs and mutton for lunch" or "slept about 5 hours, pretty restless"
7. **Available via CLI or Web** — Terminal interface for power users, mobile-friendly web UI for on-the-go
8. **Multiple LLM providers** — Claude, Gemini, OpenAI, Groq, or local Ollama

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   User Interfaces                       │
│                                                         │
│  ┌─────────────────┐      ┌──────────────────────────┐  │
│  │   CLI (run_cli) │      │   Web UI (run_web)       │  │
│  │   rich + prompt │      │   FastAPI + React PWA    │  │
│  │   --default     │      │   Streaming responses    │  │
│  │   --smart       │      │   Mobile-first           │  │
│  │   --verbose     │      │   Installable (PWA)      │  │
│  │   --quiet       │      │   HTTP Basic Auth        │  │
│  └────────┬────────┘      └────────────┬─────────────┘  │
│           │                            │                │
│           └──────────┬─────────────────┘                │
│                      ▼                                  │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Agent Loop (agent.py)                  │
│                                                         │
│  1. User message + last_exchange (for follow-ups)       │
│  2. System prompt built from:                           │
│     - Static profile (profile.json)                     │
│     - Dynamic context (recent data from all tables)     │
│     - Nutrition alerts (3-day rolling)                  │
│     - recent_logs (for "change that" corrections)       │
│  3. LLM decides: respond OR call tool(s)                │
│  4. If tool → execute → feed result back → loop         │
│  5. Repeat until LLM produces final response            │
│                                                         │
│  (No full conversation history — but tracks recent_logs │
│   and last_exchange for corrections and follow-ups)     │
└──────────┬──────────────────────────────────────────────┘
           │
     ┌─────▼─────────────────────────────┐
     │  LLM Provider (llm/)              │
     │                                   │
     │  • Claude (Anthropic) — default   │
     │  • Gemini (Google) — free tier    │
     │  • OpenAI                         │
     │  • Groq — limited free tier       │
     │  • Ollama — local models          │
     └─────┬─────────────────────────────┘
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
     │  • medications             │
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
| LLM | Claude (default), Gemini, OpenAI, Groq, Ollama | Provider abstraction via `llm/` |
| Database | SQLite (WAL mode) | Zero setup, file-based, perfect for personal tools |
| CLI | `rich` + `prompt_toolkit` | Beautiful terminal UI |
| Web Backend | FastAPI + SSE streaming | Lightweight, async, real-time responses |
| Web Frontend | React + Tailwind (CDN) | Mobile-first, no build step |
| PWA | Service worker + manifest | Installable on phone, offline app shell |
| Profile | JSON file | Static medical data, injected into system prompt |
| Nutrition | LLM estimates | No external API — LLM knows food nutrition |
| Auth | HTTP Basic Auth | Username/password via `.env` file |
| Remote Access | Cloudflare Tunnel | Free, no static IP needed |

### LLM Provider Comparison

| Provider | Status | Cost | Notes |
|----------|--------|------|-------|
| Claude | ✅ Best | Paid | Best reasoning and tool calling |
| Gemini | ✅ Recommended | Free tier | Good quality, generous free tier |
| OpenAI | ✅ Works | Paid | Good quality |
| Groq | ⚠️ Limited | Free tier | May hit token limits with full system prompt (~9600 tokens) |
| Ollama | ⚠️ Unreliable | Free (local) | Small models (8B) struggle with complex tool calling |

### Current limitations

| Component | Status | Notes |
|-----------|--------|-------|
| Web streaming | Claude only | LLM abstraction not yet implemented for web |
| Hosting | Tunnel only | Permanent URL requires purchased domain |
| Vector DB | Not built | RAG over IBD research deferred |

---

## Project Structure

```
gutagent_project/
├── .gitignore
├── .env                          # Auth credentials + API keys (gitignored)
├── .env.example                  # Example env file for new users
├── requirements.txt
├── data/
│   ├── gutagent.db*              # SQLite database (all dynamic data)
│   ├── profile.json              # Static medical profile (gitignored)
│   └── profile_template.json     # Empty template for new users
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md           # Detailed technical documentation
│   ├── TODO.md
│   ├── MOBILE_ARCHITECTURE.md    # Mobile app planning doc
│   └── SERVER_SETUP.md           # Linux server deployment guide
├── gutagent/
│   ├── __init__.py
│   ├── run_cli.py                # Entry point — CLI chat loop
│   ├── run_web.py                # Entry point — Web server
│   ├── agent.py                  # Core agent loop (LLM + tool dispatch)
│   ├── config.py                 # Tool definitions, model config
│   ├── profile.py                # Profile loading/saving
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py             # FastAPI app + streaming endpoint + auth
│   ├── web/
│   │   ├── index.html            # Entry HTML + styles
│   │   ├── app.jsx               # React chat UI
│   │   ├── sw.js                 # Service worker (offline caching)
│   │   └── manifest.json         # PWA manifest
│   ├── llm/                      # LLM provider abstraction
│   │   ├── __init__.py           # get_provider() factory
│   │   ├── base.py               # BaseLLMProvider interface
│   │   ├── claude.py             # Claude/Anthropic provider
│   │   ├── gemini_provider.py    # Google Gemini provider
│   │   ├── openai_provider.py    # OpenAI provider
│   │   ├── groq_provider.py      # Groq provider
│   │   └── ollama_provider.py    # Ollama (local) provider
│   ├── tools/
│   │   ├── __init__.py
│   │   └── registry.py           # All tool handlers + dispatch
│   ├── db/
│   │   ├── __init__.py
│   │   └── models.py             # All DB operations (schema + CRUD)
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── system.py             # System prompt builder (static + dynamic + alerts)
│   ├── rag/                      # Empty — future use
│   └── utils/
│       └── check_data.py         # Query DB with filters and args
└── tests/
```

### Design decisions

**Consolidated tool handlers** — All handlers in `registry.py`, all DB ops in `models.py`. Each handler is 5-10 lines. Split into separate files only when a module exceeds ~300 lines.

**Profile vs Database** — Static facts (conditions, family history, dietary rules) live in `profile.json`. Dynamic data (meals, symptoms, vitals, sleep, exercise, etc.) lives in the database. System prompt pulls from both sources every API call.

**Dynamic context includes everything** — At session start, the LLM sees recent data from all tables (meals, symptoms, vitals, sleep, exercise, meds, labs, journal) plus nutrition alerts. This eliminates redundant queries. `query_logs` is for searching further back or filtering.

**LLM interprets, code fetches** — No complex analysis code. Tools fetch data, the LLM interprets patterns. This works better than coded correlation engines.

**LLM estimates nutrition** — No external nutrition API. The LLM directly estimates calories, protein, and micronutrients for any food (including regional cuisines like Indian). More reliable than API lookups for diverse foods.

**No ORM** — Direct SQLite with `sqlite3.Row` for dict-like access. Simpler, fewer dependencies, good enough for a personal tool.

**All timestamps local** — No UTC conversion. `occurred_at` is always local time (inferred by the LLM from context or set to current time). Easier to read and reason about.

**Two interfaces, one agent** — Both CLI and web use the same `agent.py`. The agent is interface-agnostic.

**Provider abstraction** — `llm/` directory contains provider implementations. CLI uses the abstraction; web streaming still hardcoded to Claude (pending).

---

## Running the App

### CLI
```bash
python -m gutagent.run_cli
```

| Command               | Effect |
|-----------------------|--------|
| `--default`           | Use default model (faster, cheaper) |
| `--smart`             | Use smart model (better analysis) |
| `--verbose`           | Show tool calls |
| `--quiet`             | Hide tool calls (default) |
| `quit`/`exit`/`q`/`x` | End session |

To use a different LLM provider, set in `.env`:
```bash
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
```

Or via environment variable:
```bash
export LLM_PROVIDER=gemini
python -m gutagent.run_cli
```

### Web
```bash
python -m gutagent.run_web
```

Opens at `http://localhost:8000`. Access from phone on same WiFi via the network URL shown.

| Feature | Description |
|---------|-------------|
| Model toggle | Switch Default/Smart in settings |
| Show tools | Toggle tool call visibility in settings |
| Quick actions | Pre-filled prompts for common logging |
| PWA install | Add to home screen on mobile |

### Authentication

For remote access, create a `.env` file:
```bash
GUTAGENT_USERNAME=your_username
GUTAGENT_PASSWORD=your_password
```

Server shows `🔒 Auth enabled` on startup when credentials are set. Auth is disabled if not set (for local development).

### Remote Access (Cloudflare Tunnel)

```bash
# Install cloudflared (macOS)
brew install cloudflared

# Start tunnel (in separate terminal)
cloudflared tunnel --url http://localhost:8000

# Use the generated URL from phone/anywhere
```

The tunnel URL changes each restart (free tier). For a permanent URL, purchase a domain and configure Cloudflare. See `docs/SERVER_SETUP.md` for details.

---

## LLM Provider Layer

The `llm/` directory provides a unified interface for multiple LLM providers:

```python
# llm/__init__.py
def get_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Factory function - returns appropriate provider based on config."""
    provider = provider_name or os.getenv("LLM_PROVIDER", "claude")
    
    if provider == "claude":
        return ClaudeProvider()
    elif provider == "gemini":
        return GeminiProvider()
    elif provider == "openai":
        return OpenAIProvider()
    elif provider == "groq":
        return GroqProvider()
    elif provider == "ollama":
        return OllamaProvider()
```

### Base Interface

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def chat(self, messages, system_prompt, tools, model) -> LLMResponse:
        """Send a chat completion request."""
        pass
    
    @abstractmethod
    def get_model(self, model_type: str) -> str:
        """Get the model name for 'default' or 'smart'."""
        pass

@dataclass
class LLMResponse:
    content: list[ContentBlock]  # Text or tool calls
    stop_reason: str             # "end_turn" or "tool_use"
```

### Provider-Specific Notes

**Claude** — Uses native Anthropic SDK. Best tool calling accuracy.

**Gemini** — Uses `google-genai` SDK (not deprecated `google-generativeai`). Good free tier. Requires `Part.from_text(text=...)` with keyword argument.

**OpenAI** — Uses OpenAI SDK. Compatible message format.

**Groq** — Uses OpenAI-compatible API. Free tier has 6000 TPM limit which may be too small for full system prompt (~9600 tokens).

**Ollama** — Local models. Response objects use attributes (not dict methods). JSON arguments returned as strings need parsing. Small models (8B) unreliable for complex tool selection.

---

## Web UI Architecture

### Backend (api/server.py)

FastAPI server with:
- `POST /api/chat` — Streaming chat endpoint (SSE)
- `GET /api/context` — Get current dynamic context
- `GET /api/profile` — Get user profile
- HTTP Basic Auth on all endpoints (if credentials configured)
- Static file serving for web UI

Session state (in-memory, resets on server restart):
- `recent_logs` — tracks recently logged entries for corrections
- `last_exchange` — tracks last Q&A for follow-up context

### Frontend (web/)

React app loaded via CDN (no build step):
- `index.html` — Entry point, Tailwind config, markdown styles
- `app.jsx` — Chat UI, settings panel, quick actions
- `sw.js` — Service worker for offline caching
- `manifest.json` — PWA configuration

### Streaming Flow

```
Browser                    Server                     Claude API
   │                          │                            │
   │  POST /api/chat          │                            │
   │  {message, session_id}   │                            │
   │ ─────────────────────►   │                            │
   │                          │  messages.stream()         │
   │                          │ ──────────────────────►    │
   │                          │                            │
   │                          │  ◄── text delta ───────    │
   │  ◄─ SSE: {type: text} ── │                            │
   │                          │  ◄── text delta ───────    │
   │  ◄─ SSE: {type: text} ── │                            │
   │                          │                            │
   │                          │  ◄── tool_use ─────────    │
   │  ◄─ SSE: {type: tool} ── │                            │
   │                          │                            │
   │                          │  [execute tool locally]    │
   │                          │                            │
   │                          │  tool_result ──────────►   │
   │                          │                            │
   │                          │  ◄── text delta ───────    │
   │  ◄─ SSE: {type: text} ── │                            │
   │                          │                            │
   │  ◄─ SSE: {type: done} ── │                            │
   │                          │                            │
```

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

The LLM always has this context without needing to query. Tools are for deeper searches or longer time ranges.

---

## Database Schema

All timestamps are **local time** (no UTC).

### meals
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| occurred_at | TIMESTAMP | When meal was eaten (inferred by LLM from context) |
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

### medications
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| medication | TEXT | Name of medication (or full med list for snapshots) |
| event_type | TEXT | started, stopped, dose_changed |
| occurred_at | TIMESTAMP | When event happened |
| dose | TEXT | Dose information |
| notes | TEXT | Additional context |

`snapshot` event type stores medication state at a point in time (e.g., doctor visits). The full medication timeline is dumped into the system prompt — the LLM interprets the history rather than code trying to parse it.

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
| servings | REAL | Number of servings the recipe makes (default 1) |
| calories | REAL | Per-serving calories |
| protein | REAL | Per-serving protein (g) |
| carbs | REAL | Per-serving carbs (g) |
| fat | REAL | Per-serving fat (g) |
| fiber | REAL | Per-serving fiber (g) |
| vitamin_b12 | REAL | Per-serving B12 (μg) |
| vitamin_d | REAL | Per-serving vitamin D (IU) |
| folate | REAL | Per-serving folate (μg) |
| iron | REAL | Per-serving iron (mg) |
| zinc | REAL | Per-serving zinc (mg) |
| magnesium | REAL | Per-serving magnesium (mg) |
| calcium | REAL | Per-serving calcium (mg) |
| potassium | REAL | Per-serving potassium (mg) |
| omega_3 | REAL | Per-serving omega-3 (g) |
| vitamin_a | REAL | Per-serving vitamin A (IU) |
| vitamin_c | REAL | Per-serving vitamin C (mg) |
| notes | TEXT | Recipe notes |
| created_at | TIMESTAMP | When recipe was saved |

When saving a recipe, the LLM provides total ingredient nutrition and servings count. The system calculates and stores **per-serving** nutrition by dividing totals by servings. When logging a meal using a recipe, the stored per-serving nutrition is used directly.

### meal_items
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| meal_id | INTEGER | Foreign key to meals |
| food_name | TEXT | Individual food item or recipe name |
| quantity | REAL | Amount |
| unit | TEXT | g, piece, cup, serving, etc. |

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
| vitamin_d | REAL | IU |
| folate | REAL | μg |
| iron | REAL | mg |
| zinc | REAL | mg |
| magnesium | REAL | mg |
| calcium | REAL | mg |
| potassium | REAL | mg |
| omega_3 | REAL | g |
| vitamin_a | REAL | IU |
| vitamin_c | REAL | mg |

---

## Nutrition Tracking

### How It Works

1. User mentions a meal → LLM parses into individual food items
2. LLM estimates nutrition for each item using its knowledge (no external API)
3. Tool handler sums nutrition and stores in `meal_items` + `meal_nutrition`
4. Nutrition alerts calculated on 3-day rolling average

**Recipe workflow:**
1. User saves a recipe with ingredients and servings count
2. System calculates per-serving nutrition and stores in recipes table
3. When logging a meal with a recipe, the stored per-serving values are used directly
4. Recipe name is stored as a single meal_item entry

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
- System prompt (LLM sees them proactively)
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
- User describes ingredients and servings → LLM saves with `save_recipe`
- System calculates and stores per-serving nutrition
- When logging a meal, LLM checks for matching recipe and uses stored nutrition

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
| `save_recipe` | Save a recipe with ingredients and per-serving nutrition |
| `get_recipe` | Retrieve a saved recipe with nutrition |
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

Allowed tables: meals, symptoms, vitals, medications, sleep, exercise, journal.

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
    "other": []
  },
  "upcoming_appointments": {}
}
```

Users expand this structure as needed. The template is minimal; individual profiles can have detailed nested structures.

---

## Agent Loop (agent.py)

```python
# Include last_exchange for follow-up context
messages = []
if last_exchange.get("user") and last_exchange.get("assistant"):
    messages.append({"role": "user", "content": last_exchange["user"]})
    messages.append({"role": "assistant", "content": last_exchange["assistant"]})
messages.append({"role": "user", "content": user_message})

while iteration < max_iterations:
    response = provider.chat(
        messages=messages,
        system_prompt=system_prompt,  # Static + dynamic + recent_logs
        tools=TOOLS,
        model=model
    )
    
    if response.stop_reason == "tool_use":
        # Extract tool calls from response
        # Execute each via registry.execute_tool()
        # Track log operations in recent_logs
        # Append tool_use and tool_result to messages
        # Loop again — LLM sees results and decides next action
    else:
        # Extract text response
        # Update recent_logs with entries from this turn
        # Update last_exchange for next turn
        # Return response
```

Key points:
- No full conversation history — but tracks recent_logs and last_exchange
- `recent_logs` enables "change that to 5" corrections without specifying IDs
- `last_exchange` enables follow-ups like "yes" or "that's right"
- Dynamic context in system prompt provides continuity (recent meals, symptoms, etc.)
- LLM can call multiple tools in a single response
- Message flow: user → assistant(tool_use) → user(tool_result) → assistant(text)
- Max iterations prevent infinite loops
- Model switchable at runtime via settings (web) or flags (CLI)
- Provider switchable via `LLM_PROVIDER` env var

---

## Data Flow Examples

### "I had eggs and mutton with ghee for lunch"
1. User message → agent loop
2. LLM calls `log_meal` with itemized nutrition:
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
4. Result returned to LLM → "Logged your lunch: eggs and mutton with ghee (~540 cal, 37g protein)."

### "Had masala tea for breakfast"
1. LLM recognizes saved recipe "Masala tea"
2. LLM calls `log_meal` with `recipe_name="Masala tea"`:
   ```json
   {
     "meal_type": "breakfast",
     "description": "masala tea",
     "recipe_name": "Masala tea"
   }
   ```
3. Registry fetches recipe's per-serving nutrition, stores in meal_nutrition
4. Result: "Logged breakfast using your Masala tea recipe — 52 cal, 2.7g protein."

### "I'm feeling bloated"
1. LLM asks severity first (prompt rule — never guess)
2. User says "about a 5"
3. LLM calls `log_symptom(symptom="bloating", severity=5)`
4. LLM already has recent meals in dynamic context, notes potential triggers

### "How's my nutrition?"
1. LLM calls `get_nutrition_summary(days=3)`
2. Reviews totals and daily averages
3. Mentions any alerts (e.g., "You're low on vitamin C this week")

### "Remember that I have hypohidrosis"
1. LLM calls `update_profile(section="conditions.chronic", action="append", value="Hypohidrosis (lifelong reduced sweating, poor heat tolerance)")`
2. Profile updated, persists across sessions

### "Save that test suggestion"
1. LLM calls `update_profile(section="suggestions.tests_to_request", action="append", value="B12 levels — fatigue and neurological symptoms")`
2. Saved for future doctor visits

### "Save my dal tadka recipe — makes 4 servings"
1. User describes ingredients
2. LLM calls `save_recipe` with ingredients, total nutrition, and servings=4
3. System divides nutrition by 4, stores per-serving values
4. Next time user logs "dal tadka", LLM uses `recipe_name` parameter

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
| Phase 4 | ⏭️ Skipped | RAG knowledge base (deferred — LLM knowledge + web search sufficient) |
| Phase 5 | ✅ Done | Nutrition tracking (LLM estimates, no external API) |
| Phase 6 | ✅ Done | Web UI (FastAPI + React PWA, streaming, mobile-first) |
| Phase 7 | 🔶 Partial | Auth (done), remote hosting (Cloudflare tunnel works, permanent URL pending) |
| Phase 8 | 🔶 Partial | LLM abstraction (CLI supports all providers, web hardcoded to Claude) |
| Phase 9 | 🔲 Planned | Setup wizard for new users |
| Phase 10 | 🔲 Planned | Profile restructure + insights storage |

---

## API Costs

Rough estimates per message exchange:

| Provider | Default Model | Smart Model |
|----------|---------------|-------------|
| Claude | ~$0.002 (Haiku) | ~$0.02 (Sonnet) |
| Gemini | Free (Flash) | Free (Pro) |
| OpenAI | ~$0.002 (GPT-4o-mini) | ~$0.02 (GPT-4o) |
| Groq | Free | Free |
| Ollama | Free (local) | Free (local) |

Using Haiku for routine logging and Sonnet for analysis keeps costs low (~$1-2/month for typical use). Gemini is the recommended free alternative.

---

## Making It Shareable

The codebase separates generic from personal:

**Generic (same for everyone):**
- Agent loop, tool calling, message handling
- Database schema
- All tool definitions and handlers
- System prompt structure
- Web UI (frontend + backend)
- Utility scripts (check_data.py)
- `profile_template.json`
- `.env.example`

**Personal (different per user):**
- `profile.json` (each user fills in their own)
- `gutagent.db` (each user's data)
- `.env` (each user's API keys and auth)

To share: a new user copies `profile_template.json` to `profile.json`, copies `.env.example` to `.env`, fills in their details, and starts logging.

---

## Testing

Run tests before committing changes:

```bash
pytest tests/test_gutagent.py -v
```

**Coverage:**

| File | Tested | Notes |
|------|--------|-------|
| `models.py` | ✅ | All database functions |
| `registry.py` | ✅ | All handlers via `execute_tool()` |
| `profile.py` | ✅ | load/save/update profile |
| `config.py` | ❌ | Static tool definitions |
| `system.py` | ❌ | Static prompt text |
| `context.py` | ❌ | Builds API context |

Tests use a temporary database — your real data is never touched.

**When to run tests:**
- After editing `models.py` — run all tests
- After editing `registry.py` — run `pytest tests/test_gutagent.py::TestRegistry -v`
- After editing `profile.py` — run `pytest tests/test_gutagent.py::TestProfile -v`

---

## Next Steps

1. **Web streaming abstraction** — Make web UI use provider layer (currently hardcoded to Claude)
2. **Setup wizard** — Guided first-run for new users
3. **Profile restructure** — Better organization of static vs dynamic data, add insights/correlations storage
4. **Offline queue** — Queue messages when offline, sync when back online
5. **Permanent URL** — Purchase domain, configure Cloudflare for stable remote access
