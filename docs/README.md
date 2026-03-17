# GutAgent 🧬

A personalized dietary AI agent for managing inflammatory bowel disease. Built with Claude's API and function calling — no frameworks, full control.

## What it does

- **Knows your medical profile** — conditions, triggers, medications, labs
- **Logs everything naturally** — meals, symptoms, vitals, sleep, exercise, journal
- **Tracks nutrition** — calories, protein, and 11 micronutrients for every meal
- **Alerts on deficiencies and excesses** — warns when nutrients fall below recommended levels or exceed safe limits
- **Finds patterns** — Claude interprets your data to identify correlations
- **Remembers what matters** — save test suggestions, update your profile conversationally
- **Saves recipes with nutrition** — track nutrition consistently for dishes you eat often; recipes store per-serving nutrition
- **Works anywhere** — CLI for terminal, mobile-friendly web UI for on-the-go
- **Multiple LLM providers** — Claude, Gemini, OpenAI, Groq, or local Ollama

## Quick Start

```bash
# Clone and enter the project
cd gutagent_project

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up your .env file (copy from example)
cp .env.example .env
# Edit .env with your API key and auth credentials

# Edit your medical profile
cp data/profile_template.json data/profile.json
# Then customize data/profile.json with your info

# Run CLI
python -m gutagent.run_cli

# Or run Web UI
python -m gutagent.run_web
# Then open http://localhost:8000
```

## LLM Providers

GutAgent supports multiple LLM providers. Set `LLM_PROVIDER` in your `.env` file:

| Provider | Status | Cost | Notes |
|----------|--------|------|-------|
| `claude` | ✅ Best | Paid (~$0.002-0.02/msg) | Best reasoning and tool calling |
| `gemini` | ✅ Recommended | Free tier | Good quality, generous free tier |
| `openai` | ✅ Works | Paid (~$0.002-0.02/msg) | Good quality |
| `groq` | ⚠️ Limited | Free tier | May hit token limits with full system prompt |
| `ollama` | ⚠️ Unreliable | Free (local) | Small models struggle with complex tool calling |

### Setup by Provider

**Gemini (Recommended free option):**
```bash
pip install google-genai
# Get API key at https://makersuite.google.com/app/apikey
# Add to .env:
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_key_here
```

**Claude:**
```bash
# Add to .env:
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**OpenAI:**
```bash
pip install openai
# Get API key at https://platform.openai.com/api-keys
# Add to .env:
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

**Groq:**
```bash
pip install groq
# Get API key at https://console.groq.com
# Add to .env:
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your-key-here
```

**Ollama (local):**
```bash
pip install ollama
ollama pull llama3.1:8b
# Add to .env:
LLM_PROVIDER=ollama
```

## Authentication

For remote access (via Cloudflare tunnel), HTTP Basic Auth is enabled.

Add to your `.env` file:
```bash
GUTAGENT_USERNAME=your_username
GUTAGENT_PASSWORD=your_secure_password
```

The server shows `🔒 Auth enabled` on startup when credentials are configured.

## Usage

Just talk to it naturally:

```
You: I had chicken with lettuce and tomato for lunch
GutAgent: Logged lunch: chicken, lettuce, tomato (~380 cal, 35g protein). 
         Good protein and vitamin C from the tomato!

You: I'm feeling bloated, about a 5
GutAgent: Logged bloating (severity 5). You had sev for breakfast — that's chickpea 
         flour, which has been triggering bloating consistently for you.

You: Slept maybe 5 hours, pretty restless
GutAgent: Logged — 5 hours, restless. That's below what you need. How are you 
         feeling energy-wise?

You: Went for a 20 minute walk this morning
GutAgent: Nice! Logged your walk. That's your first exercise entry this week.

You: My BP this morning was 128/82 pulse 68
GutAgent: Logged — 128/82, HR 68. That's better than your readings last week.

You: How's my nutrition lately?
GutAgent: Over the last 3 days: averaging 1800 cal, 85g protein. You're a bit 
         low on vitamin C (45% of target) — might want to add some citrus or 
         bell peppers.

You: Remember that I have hypohidrosis — I barely sweat
GutAgent: Added to your profile under chronic conditions. I'll keep this in mind.

You: Had masala tea for breakfast
GutAgent: Logged breakfast using your Masala tea recipe — 52 cal, 2.7g protein, 
         good calcium from the milk.
```

## Running the App

### CLI
```bash
python -m gutagent.run_cli
```

| Command               | Effect |
|-----------------------|--------|
| `--default`           | Use Default model (faster, cheaper) |
| `--smart`             | Use Smart model (better reasoning) |
| `--verbose`           | Show tool calls |
| `--quiet`             | Hide tool calls (default) |
| `quit`/`exit`/`q`/`x` | Exit |

### Web UI
```bash
python -m gutagent.run_web
```

Opens at `http://localhost:8000`. Access from phone on same WiFi using the network URL shown.

| Feature | Description |
|---------|-------------|
| Streaming | Responses appear word-by-word |
| Model toggle | Switch Default/Smart in settings |
| Show tools | Toggle tool call visibility |
| Quick actions | One-tap buttons for common logging |
| PWA install | Add to home screen on mobile |

**To install on phone:**
- iOS Safari: Share → "Add to Home Screen"
- Android Chrome: Menu → "Add to Home Screen"

### Remote Access (Cloudflare Tunnel)

Access from anywhere, not just home WiFi:

```bash
# Install cloudflared
brew install cloudflared  # or see cloudflare docs for Linux

# Start tunnel (gives you a public URL)
cloudflared tunnel --url http://localhost:8000
```

For permanent setup, see `docs/SERVER_SETUP.md`.

## Project Structure

```
gutagent_project/
├── gutagent/
│   ├── run_cli.py       # CLI entry point
│   ├── run_web.py       # Web server entry point
│   ├── agent.py         # Core agent loop
│   ├── config.py        # Model settings + tool definitions
│   ├── profile.py       # Medical profile loading/saving
│   ├── api/
│   │   └── server.py    # FastAPI backend
│   ├── web/
│   │   ├── index.html   # Web UI entry point
│   │   ├── app.jsx      # React chat interface
│   │   ├── sw.js        # Service worker (offline)
│   │   └── manifest.json # PWA config
│   ├── llm/             # LLM provider abstraction
│   │   ├── __init__.py  # Provider factory
│   │   ├── base.py      # Base classes
│   │   ├── claude.py    # Anthropic Claude
│   │   ├── gemini_provider.py   # Google Gemini
│   │   ├── openai_provider.py   # OpenAI
│   │   ├── groq_provider.py     # Groq
│   │   └── ollama_provider.py   # Ollama (local)
│   ├── tools/
│   │   └── registry.py  # Tool dispatch
│   ├── db/
│   │   └── models.py    # SQLite operations
│   ├── prompts/
│   │   └── system.py    # System prompt builder
│   └── utils/
│       └── check_data.py    # Query DB from command line
├── tests/
├── data/
│   ├── profile.json         # Your medical profile (gitignored)
│   ├── profile_template.json
│   └── gutagent.db          # SQLite database (auto-created)
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md           # Detailed technical documentation
│   ├── TODO.md
│   ├── MOBILE_ARCHITECTURE.md    # Mobile app planning doc
│   └── SERVER_SETUP.md           # Linux server deployment guide
├── .gitignore
├── .env                      # Auth credentials + API keys (gitignored)
├── .env.example              # Example env file for new users
└── requirements.txt
```

## Tools

| Tool | What it does |
|------|--------------|
| `log_meal` | Log what you ate with nutrition estimates |
| `log_symptom` | Log symptoms with severity |
| `log_vital` | Log BP, weight, temperature, etc. |
| `log_medication_event` | Track medication starts, stops, changes |
| `log_sleep` | Log sleep hours and quality |
| `log_exercise` | Log physical activity |
| `log_journal` | Freeform notes and life events |
| `query_logs` | Search meals, symptoms, vitals, meds, labs, sleep, exercise |
| `get_profile` | Retrieve your medical profile |
| `correct_log` | Fix or delete logged entries |
| `update_profile` | Add/update profile data conversationally |
| `save_recipe` | Save a recipe with ingredients and per-serving nutrition |
| `get_recipe` | Retrieve a saved recipe with nutrition |
| `list_recipes` | List all saved recipes |
| `delete_recipe` | Delete a recipe |
| `get_nutrition_summary` | Get nutrition totals and averages |
| `get_nutrition_alerts` | Get deficiency and excess alerts |

## Nutrition Tracking

Every meal is automatically tracked for:

**Macros:** calories, protein, carbs, fat, fiber

**Micronutrients:** B12, vitamin D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, vitamin A, vitamin C

The LLM estimates nutrition directly — no external API needed. Works great for any cuisine including Indian food.

**Recipes:** Save recipes with ingredients and the system calculates per-serving nutrition. When you log a meal using a recipe, the stored nutrition is used directly for consistency.

**Alerts:** When your 3-day average falls below 70% of recommended daily intake or exceeds safe upper limits, you'll see a warning.

## Dynamic Context

At session start, the LLM automatically sees:
- Your full medication timeline
- Latest lab results
- Recent vitals (7 days)
- Recent meals (3 days) with nutrition
- Recent symptoms (7 days)
- Recent sleep (7 days)
- Recent exercise (7 days)
- Recent journal entries (7 days)
- Saved recipes with nutrition
- Nutrition alerts

No need to query — the LLM already has context. Use `query_logs` for deeper searches or longer time ranges.

## Environment Variables

Create a `.env` file in the project root:

```bash
# Authentication (required for remote access)
GUTAGENT_USERNAME=your_username
GUTAGENT_PASSWORD=your_secure_password

# LLM Provider (choose one)
LLM_PROVIDER=gemini  # or claude, openai, groq, ollama

# API Keys (only need one, matching your provider)
GOOGLE_API_KEY=your_gemini_key
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# GROQ_API_KEY=gsk_...
```

## Build Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Done | Python fundamentals, environment setup |
| Phase 1 | ✅ Done | Core agent loop, tool calling, CLI |
| Phase 2 | ✅ Done | Meal/symptom/vitals/meds logging, corrections |
| Phase 3 | ✅ Done | Sleep/exercise/journal, profile updates, pattern interpretation |
| Phase 4 | ⏭️ Skipped | RAG knowledge base (deferred) |
| Phase 5 | ✅ Done | Nutrition tracking with LLM estimates |
| Phase 6 | ✅ Done | Web UI (FastAPI + React PWA) |
| Phase 7 | 🔶 Partial | Auth ✅, Cloudflare tunnel ✅, permanent URL pending |
| Phase 8 | 🔶 Partial | LLM abstraction (CLI ✅, web streaming hardcoded to Claude) |
| Phase 9 | 🔲 Planned | Setup wizard for new users |

## Design Philosophy

- **No frameworks** — raw LLM API calls so you understand every step
- **LLM interprets** — no complex analysis code; the LLM reads your data and finds patterns
- **LLM estimates nutrition** — no external API; works for any cuisine
- **Profile + Database** — static facts in JSON, dynamic data in SQLite
- **Dynamic context** — LLM sees recent data automatically, queries only for deeper dives
- **Two interfaces, one agent** — CLI and web UI share the same core logic
- **Conversational** — just talk naturally, the agent figures out what to log
- **Provider agnostic** — switch between Claude, Gemini, OpenAI, etc.

## Testing

Run tests before committing changes to `models.py`, `registry.py`, or `profile.py`:

```bash
# Run all tests
pytest tests/test_gutagent.py -v

# Run specific test class
pytest tests/test_gutagent.py::TestMeals -v

# Stop on first failure
pytest tests/test_gutagent.py -x
```

Tests use a temporary database — your real data is never touched.

## Related Docs

- `ARCHITECTURE.md` — Detailed technical documentation
- `SERVER_SETUP.md` — Linux server deployment guide
- `MOBILE_ARCHITECTURE.md` — Mobile app planning and options
