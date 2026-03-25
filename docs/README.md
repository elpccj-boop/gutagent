# GutAgent 🧬

A personalized dietary AI agent for tracking food, symptoms, vitals, and health patterns. Supports Claude, Gemini, and OpenAI.

## What It Does

- **Knows your medical profile** — conditions, triggers, medications, preferences
- **Logs everything naturally** — meals, symptoms, vitals, labs, sleep, exercise, journal
- **Tracks nutrition** — macros + 11 micronutrients for every meal
- **Finds patterns** — the LLM interprets your data to identify correlations
- **Saves recipes** — store per-serving nutrition for consistent tracking
- **Works anywhere** — CLI for terminal, mobile-friendly web UI for on-the-go

## Quick Start

```bash
# Clone and setup
cd gutagent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
mkdir -p data
cp gutagent/profile_template.json data/profile.json
# Edit .env with your API key
# Edit data/profile.json with your medical info

# Run
python -m gutagent.run_cli    # Terminal
python -m gutagent.run_web    # Web UI at http://localhost:8000
```

## Configuration

Create a `.env` file in the project root:

```bash
# LLM Provider
LLM_PROVIDER=claude          # claude, gemini, or openai

# API Key (only need the one for your chosen provider)
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...

# Claude Cache TTL (optional, default 5 min)
# CLAUDE_CACHE_TTL=1h        # Set to "1h" for 1-hour cache

# Web Authentication (optional, for remote access)
GUTAGENT_USERNAME=yourname
GUTAGENT_PASSWORD=yourpassword
```

### LLM Providers

| Provider | Default | Smart | Cost (per 1M tokens) | Streaming | Caching |
|----------|---------|-------|----------------------|-----------|---------|
| Claude | Haiku 4.5 | Sonnet 4.5 | $1/$5 — $3/$15 | ✅ | 5min/1h, 90% discount |
| Gemini | 2.5 Flash | 2.5 Pro | $0.30/$2.50 — $1.25/$10 | ✅ | 1h, 90% discount |
| OpenAI | GPT-4o-mini | GPT-4o | $0.15/$0.60 — $2.50/$10 | ✅ | Auto, 50% discount |

*Cost format: input/output per million tokens*

## Usage

Just talk naturally:

```
You: I had chicken curry and rice for lunch
GutAgent: Logged lunch — chicken curry with rice (~520 cal, 35g protein).

You: Feeling bloated, about a 5
GutAgent: Logged bloating (severity 5). You had chickpea flour yesterday — 
         that's been a consistent trigger for you.

You: Slept maybe 5 hours, pretty restless
GutAgent: Logged — 5 hours, restless. That's below your usual.

You: BP this morning was 128/82 pulse 68
GutAgent: Logged — 128/82, HR 68. Trending better than last week.

You: How's my nutrition lately?
GutAgent: Last 3 days: averaging 1800 cal, 85g protein. You're low on 
         vitamin C (45% of target) — consider adding citrus or peppers.

You: Change that severity to 4
GutAgent: Updated bloating severity from 5 to 4.
```

## Running

### CLI

```bash
python -m gutagent.run_cli
```

Commands: `--verbose`, `--quiet`, `--default`, `--smart`, `quit`

### Web UI

```bash
python -m gutagent.run_web
```

Opens at `http://localhost:8000`. Features:
- Streaming responses
- Model toggle (Default/Smart)
- Quick action buttons
- PWA installable on mobile

### Remote Access

```bash
# Install cloudflared
brew install cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

Set `GUTAGENT_USERNAME` and `GUTAGENT_PASSWORD` in `.env` for authentication.

## Project Structure

```
gutagent/
├── run_cli.py          # CLI entry point
├── run_web.py          # Web server entry point
├── agent.py            # CLI agent loop
├── core.py             # Shared logic (CLI + web)
├── config.py           # Tool definitions, model config
├── profile.py          # Profile loading/saving
├── paths.py            # Centralized path management
├── logging_config.py   # Logging setup
├── profile_template.json # Template for new users
├── api/server.py       # FastAPI + streaming
├── web/                # React PWA frontend
├── llm/                # Provider abstraction (Claude, Gemini, OpenAI)
├── tools/registry.py   # Tool handlers
├── db/                 # Database layer
│   ├── connection.py   # DB setup, schema
│   ├── common.py       # Shared utilities
│   ├── logs.py         # All logging operations
│   ├── recipes.py      # Recipe CRUD
│   └── nutrition.py    # RDA targets, alerts
└── prompts/system.py   # System prompt builder

data/                   # User data (gitignored, create manually)
├── profile.json        # Copy from gutagent/profile_template.json
└── gutagent.db         # SQLite database (auto-created)
```

## Tools (18)

| Category | Tools |
|----------|-------|
| Logging | `log_meal`, `log_symptom`, `log_vital`, `log_lab`, `log_medication_event`, `log_sleep`, `log_exercise`, `log_journal` |
| Query & Edit | `query_logs`, `correct_log`, `get_profile`, `update_profile` |
| Recipes | `save_recipe`, `get_recipe`, `list_recipes`, `delete_recipe` |
| Nutrition | `get_nutrition_summary`, `get_nutrition_alerts` |

## Nutrition Tracking

Every meal tracks:
- **Macros:** calories, protein, carbs, fat, fiber
- **Micros:** B12, D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, A, C

Alerts appear when 3-day averages fall below 70% of RDA or exceed safe limits.

## Testing

```bash
pytest tests/test_gutagent.py -v
```

Tests use a temporary database and profile — your data is never touched.

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Technical deep dive
- [TODO.md](docs/TODO.md) — Roadmap and known issues
- [REFACTORING.md](docs/REFACTORING.md) — Technical debt and improvements

## Known Limitations

- Single user (personal tool, no multi-user support)
- Session state in memory (lost on server restart)
- No offline queue (web UI requires connectivity)
