# GutAgent 🫚

A personalized dietary AI agent for managing inflammatory bowel disease. Built with Claude's API and raw function calling — no frameworks, full control.

## What it does

- **Knows your medical profile** — conditions, triggers, medications, labs
- **Logs meals and symptoms** automatically from natural conversation
- **Finds patterns** — correlates foods with symptoms over time
- **Suggests meals** based on what's safe for YOUR gut
- **Learns from your data** — gets smarter the more you use it

## Quick Start

```bash
# Clone and enter the project
cd gutagent

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install anthropic rich prompt-toolkit

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Edit your medical profile
# (A starter profile is included — customize data/profile.json)

# Run it!
python -m gutagent.main
```

## Usage

Just talk to it naturally:

```
You: I had chicken with lettuce and tomato for lunch
GutAgent: Logged that — chicken, lettuce, tomato for lunch. Good protein-focused choice!

You: I'm feeling bloated
GutAgent: Logged bloating. Let me check what you ate recently...
         You had lunch about 2 hours ago. Lettuce and tomato are usually safe for you.
         How severe is it, 1-10? And did you have anything else today?

You: What should I make for dinner?
GutAgent: Based on your profile, here are some options...

You: Do you see any patterns in my symptoms?
GutAgent: Looking at the last 30 days... [runs analyze_patterns]
```

## Project Structure

```
gutagent/
├── gutagent/
│   ├── main.py          # CLI entry point
│   ├── agent.py         # Core agent loop (the important one!)
│   ├── config.py        # Model settings + tool definitions
│   ├── profile.py       # Medical profile loader
│   ├── tools/
│   │   └── registry.py  # Tool dispatch
│   ├── db/
│   │   └── models.py    # SQLite operations
│   ├── rag/             # Phase 4: knowledge base (coming soon)
│   └── prompts/
│       └── system.py    # System prompt builder
├── data/
│   ├── profile.json     # Your medical profile
│   └── gutagent.db      # SQLite database (auto-created)
└── pyproject.toml
```

## Build Phases

1. ✅ **Core Agent** — Chat with tool calling (you are here!)
2. ⬜ **Food Journal** — Log meals and symptoms ✅ (built in)
3. ⬜ **Pattern Analysis** — Food-symptom correlations ✅ (built in)
4. ⬜ **RAG Knowledge Base** — IBD dietary research (add ChromaDB)
5. ⬜ **Nutrition Lookup** — USDA FoodData Central API
6. ⬜ **Web UI** — FastAPI + HTMX or Streamlit

## Next Steps

- Add more tools (nutrition lookup, recipe search)
- Build the RAG pipeline for IBD research
- Add a web interface
- Generate weekly reports for your doctor
