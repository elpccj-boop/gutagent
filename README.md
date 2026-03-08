# GutAgent 🫚

A personalized dietary AI agent for managing inflammatory bowel disease. Built with Claude's API and function calling — no frameworks, full control.

## What it does

- **Knows your medical profile** — conditions, triggers, medications, labs
- **Logs everything naturally** — meals, symptoms, vitals, sleep, exercise, journal
- **Finds patterns** — Claude interprets your data to identify correlations
- **Remembers what matters** — save test suggestions, update your profile conversationally
- **Tracks your health inputs** — food, sleep, exercise all in one place

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
GutAgent: Logged that — chicken, lettuce, tomato for lunch. Good protein-focused choice!

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

You: How am I doing?
GutAgent: [Reviews all your recent data and gives you a summary with patterns]

You: Remember that I have hypohidrosis — I barely sweat
GutAgent: Added to your profile under chronic conditions. I'll keep this in mind.

You: Save that B12 test suggestion for my doctor
GutAgent: Saved to your suggestions list for your next appointment.

You: --verbose
Verbose mode: ON
```

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
│   ├── rag/             # Phase 4: knowledge base (planned)
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
| `log_meal` | Log what you ate |
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

## Dynamic Context

At session start, Claude automatically sees:
- Your full medication timeline
- Latest lab results
- Recent vitals (7 days)
- Recent meals (3 days)
- Recent symptoms (7 days)
- Recent sleep (7 days)
- Recent exercise (7 days)
- Recent journal entries (7 days)

No need to query — Claude already has context. Use `query_logs` for deeper searches or longer time ranges.

## Build Phases

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 0 | ✅ Done | Python fundamentals, environment setup |
| Phase 1 | ✅ Done | Core agent loop, tool calling, CLI |
| Phase 2 | ✅ Done | Meal/symptom/vitals/meds logging, corrections |
| Phase 3 | ✅ Done | Sleep/exercise/journal, profile updates, pattern interpretation |
| Phase 4 | 🔲 Planned | RAG knowledge base with IBD research |
| Phase 5 | 🔲 Planned | USDA nutrition API |
| Phase 6 | 🔲 Planned | Web UI |

## Design Philosophy

- **No frameworks** — raw Claude API calls so you understand every step
- **Claude interprets** — no complex analysis code; Claude reads your data and finds patterns
- **Profile + Database** — static facts in JSON, dynamic data in SQLite
- **Dynamic context** — Claude sees recent data automatically, queries only for deeper dives
- **Conversational** — just talk naturally, the agent figures out what to log
