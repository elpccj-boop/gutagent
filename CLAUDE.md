# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GutAgent is a personalized dietary AI agent for managing inflammatory bowel disease (IBD). It uses Claude's API with raw function calling (no frameworks) to log meals, symptoms, medications, and vitals, then analyze food-symptom correlations over time. Data is stored in SQLite; the user's medical profile lives in `data/profile.json`.

## Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install anthropic rich prompt-toolkit

# Install dev dependencies
pip install -e ".[dev]"

# Run the CLI agent
python -m gutagent.main

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_pattern_analysis.py -v

# Run a single test class or test
python -m pytest tests/test_pattern_analysis.py::TestSymptomRate -v
python -m pytest tests/test_pattern_analysis.py::TestSymptomRate::test_symptom_rate_calculation -v

# Lint
ruff check .
```

Requires `ANTHROPIC_API_KEY` environment variable to be set.

## Architecture

The agent loop is framework-free — it directly calls the Anthropic Messages API with tool definitions and handles the tool_use/tool_result cycle manually.

**Core flow:** `main.py` → `agent.run_agent()` → Claude API → tool_use → `tools/registry.py` → `db/models.py` → tool_result back to Claude → repeat until text response.

Key modules:
- **`gutagent/agent.py`** — The agentic loop. Sends messages to Claude, detects `tool_use` stop reason, executes tools via registry, feeds results back. Max 10 iterations per turn.
- **`gutagent/config.py`** — Model selection (`claude-sonnet-4-5-20250929`), `MAX_TOKENS`, and all tool JSON schemas for Claude function calling. This is where tools are defined — their names, descriptions, and `input_schema`.
- **`gutagent/tools/registry.py`** — Maps tool names to handler functions. `execute_tool()` dispatches by name. Each `_handle_*` function translates Claude's tool input into a `db/models.py` call.
- **`gutagent/db/models.py`** — All SQLite operations. Tables: `meals`, `symptoms`, `medication_events`, `vitals`, `labs`, `correlations`. Pattern analysis (`analyze_food_symptom_patterns`) correlates foods with symptoms in 0.5–8 hour windows.
- **`gutagent/prompts/system.py`** — Builds the system prompt by combining the static medical profile with dynamic context (current medications, latest labs, recent vitals) pulled directly from the database.
- **`gutagent/profile.py`** — Loads/saves `data/profile.json` (the patient's medical profile).
- **`gutagent/main.py`** — CLI entry point with Rich formatting. REPL loop with `--verbose` toggle for tool call visibility.

**Data directory:** `data/` contains `profile.json` (medical profile) and `gutagent.db` (SQLite, auto-created on first run).

**Utility scripts** in `gutagent/utils/`: `import_history.py`, `import_labs.py`, `generate_report.py`, `check_data.py`, `fix_data.py` — one-off data management scripts.

## Adding a New Tool

1. Define the tool schema in `config.py` (add to `TOOLS` list)
2. Add a `_handle_<tool_name>` function in `tools/registry.py`
3. Register it in the `handlers` dict in `execute_tool()`
4. Implement the backing database operation in `db/models.py` if needed

## Key Design Decisions

- No LLM framework (no LangChain, no CrewAI) — raw Anthropic API calls for full control and transparency
- SQLite with WAL mode for the local database
- Tool definitions use Claude's native `input_schema` format (JSON Schema)
- The system prompt is rebuilt each turn with fresh database context (meds, labs, vitals)
- `data/` directory is gitignored patient data — never commit `profile.json` or `gutagent.db`
