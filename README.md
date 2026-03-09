# GutAgent 🫚

A personalized dietary AI agent for managing inflammatory bowel disease. Built with Claude's API and function calling — no frameworks, full control.

## What it does

- **Knows your medical profile** — conditions, triggers, medications, labs
- **Logs everything naturally** — meals, symptoms, vitals, sleep, exercise, journal
- **Tracks nutrition** — calories, protein, and 11 micronutrients for every meal
- **Alerts on deficiencies and excesses** — warns when nutrients fall below recommended levels or exceed safe limits
- **Finds patterns** — Claude interprets your data to identify correlations
- **Remembers what matters** — save test suggestions, update your profile conversationally
- **Saves recipes** — track nutrition consistently for dishes you eat often

## Quick Start

```bash
# Clone and enter the project
cd gutagent_project

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install anthropic rich prompt-toolkit

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Edit your medical profile
cp data/profile_template.json data/profile.json
# Then customize data/profile.json with your info

# Run it!
python -m gutagent.main
```

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

You: Save my dal tadka recipe — it's toor dal, tomatoes, onion, garlic, cumin, turmeric, ghee
GutAgent: Saved "Dal Tadka" with 7 ingredients. Next time you have it, I'll use 
         this for consistent nutrition tracking.

You: --haiku
Model: Haiku
```

## Commands

| Command | Effect |
|---------|--------|
| `--haiku` | Use cheaper Haiku model (good for routine logging) |
| `--sonnet` | Use Sonnet model (default, better analysis) |
| `--verbose` | Show tool calls |
| `--quiet` | Hide tool calls (default) |
| `quit` | Exit |

## Project Structure

```
gutagent_project/
├── gutagent/
│   ├── main.py          # CLI entry point
│   ├── agent.py         # Core agent loop
│   ├── config.py        # Model settings + tool definitions
│   ├── profile.py       # Medical profile loading/saving
│   ├── tools/
│   │   └── registry.py  # Tool dispatch
│   ├── db/
│   │   └── models.py    # SQLite operations
│   ├── prompts/
│   │   └── system.py    # System prompt builder
│   ├── rag/             # Phase 7: knowledge base (planned)
│   └── utils/
│       ├── check_data.py    # Query DB from command line
│       └── import_labs.py   # Bulk import lab results
├── data/
│   ├── profile.json         # Your medical profile (gitignored)
│   ├── profile_template.json
│   └── gutagent.db          # SQLite database (auto-created)
└── README.md
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
| `save_recipe` | Save a recipe with ingredients |
| `get_recipe` | Retrieve a saved recipe |
| `list_recipes` | List all saved recipes |
| `delete_recipe` | Delete a recipe |
| `get_nutrition_summary` | Get nutrition totals and averages |
| `get_nutrition_alerts` | Get deficiency and excess alerts |

## Nutrition Tracking

Every meal is automatically tracked for:

**Macros:** calories, protein, carbs, fat, fiber

**Micronutrients:** B12, vitamin D, folate, iron, zinc, magnesium, calcium, potassium, omega-3, vitamin A, vitamin C

Claude estimates nutrition directly — no external API needed. Works great for any cuisine including Indian food.

**Alerts:** When your 3-day average falls below 70% of recommended daily intake or exceeds safe upper limits, you'll see a warning.

## Dynamic Context

At session start, Claude automatically sees:
- Your full medication timeline
- Latest lab results
- Recent vitals (7 days)
- Recent meals (3 days) with nutrition
- Recent symptoms (7 days)
- Recent sleep (7 days)
- Recent exercise (7 days)
- Recent journal entries (7 days)
- Saved recipes
- Nutrition alerts

No need to query — Claude already has context. Use `query_logs` for deeper searches or longer time ranges.

## API Costs

Rough estimates:
- ~$0.02 per message (Sonnet)
- ~$0.20 per day (10 messages)
- ~$5 lasts about a month

Use `--haiku` for routine logging to reduce costs by ~10x.

## Build Phases

| Phase   | Status | Description |
|---------|--------|-------------|
| Phase 0 | ✅ Done | Python fundamentals, environment setup |
| Phase 1 | ✅ Done | Core agent loop, tool calling, CLI |
| Phase 2 | ✅ Done | Meal/symptom/vitals/meds logging, corrections |
| Phase 3 | ✅ Done | Sleep/exercise/journal, profile updates, pattern interpretation |
| Phase 4 | ⏭️ Skipped | RAG knowledge base (deferred) |
| Phase 5 | ✅ Done | Nutrition tracking with Claude estimates |
| Phase 6 | 🔲 Planned | Web UI |
| Phase 7 | 🔲 Planned | RAG for IBD research if needed |

## Design Philosophy

- **No frameworks** — raw Claude API calls so you understand every step
- **Claude interprets** — no complex analysis code; Claude reads your data and finds patterns
- **Claude estimates nutrition** — no external API; works for any cuisine
- **Profile + Database** — static facts in JSON, dynamic data in SQLite
- **Dynamic context** — Claude sees recent data automatically, queries only for deeper dives
- **Conversational** — just talk naturally, the agent figures out what to log
