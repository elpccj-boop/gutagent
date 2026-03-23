# GutAgent Refactoring Plan

Technical debt and improvements identified during March 2026 review.

## Priority 1: Code Duplication

### Problem
`agent.py` and `api/server.py` duplicate ~150 lines:
- `LOG_TOOLS` dict (identical)
- `format_recent_logs()` function (identical)
- Agent loop logic (similar but one streams)

### Solution
Create `gutagent/core.py`:

```python
# gutagent/core.py

LOG_TOOLS = {
    "log_meal": "meals",
    "log_symptom": "symptoms",
    # ... etc
}

def format_recent_logs(recent_logs: dict) -> str:
    """Format recent_logs dict into a string for the prompt."""
    # ... shared implementation

def build_messages(user_message: str, last_exchange: dict) -> list:
    """Build messages list with optional last exchange context."""
    messages = []
    if last_exchange.get("user") and last_exchange.get("assistant"):
        messages.append({"role": "user", "content": last_exchange["user"]})
        messages.append({"role": "assistant", "content": last_exchange["assistant"]})
    messages.append({"role": "user", "content": user_message})
    return messages

def build_system_prompt(profile: dict, recent_logs: dict) -> tuple[str, str]:
    """Build (static, dynamic) system prompt tuple."""
    static = build_static_system_prompt(profile)
    dynamic = build_dynamic_context()
    logs_context = format_recent_logs(recent_logs)
    if logs_context:
        dynamic = dynamic + "\n\n" + logs_context
    return (static, dynamic)

def process_tool_results(response, recent_logs: dict, logs_this_turn: dict) -> dict:
    """Execute tools and track log operations. Returns tool_results for next iteration."""
    # ... shared tool execution logic
```

Then `agent.py` and `server.py` both import from `core.py`.

## Priority 2: Split models.py

### Problem
`db/models.py` is 924 lines with mixed responsibilities:
- Schema definitions
- CRUD for 10+ tables  
- RDA calculations
- Nutrition aggregation

### Solution
Split into focused modules:

```
db/
├── __init__.py          # Re-export for backward compatibility
├── connection.py        # get_connection(), init_db()
├── schema.py            # Table definitions (CREATE TABLE statements)
├── meals.py             # Meal CRUD + meal_items + meal_nutrition
├── logs.py              # symptoms, vitals, labs, meds, sleep, exercise, journal
├── recipes.py           # Recipe CRUD
├── nutrition.py         # RDA targets, alerts, summaries
└── queries.py           # Cross-table queries (get_logs_by_date, search functions)
```

Backward compatibility in `__init__.py`:
```python
# db/__init__.py
from .meals import log_meal_with_nutrition, get_recent_meals, ...
from .logs import log_symptom, log_vital, ...
from .recipes import save_recipe, get_recipe, ...
from .nutrition import get_nutrition_alerts, get_nutrition_summary, ...
```

## Priority 3: Error Handling

### Problem
Silent exception swallowing in `prompts/system.py`:
```python
try:
    meds = get_current_and_recent_meds(recent_days=30)
except Exception:
    pass  # Bug could hide here forever
```

### Solution
Add logging and let non-critical errors surface in dev:

```python
import logging
logger = logging.getLogger(__name__)

try:
    meds = get_current_and_recent_meds(recent_days=30)
except Exception as e:
    logger.warning(f"Failed to load medications for context: {e}")
    # Continue without meds in context
```

Configure logging in entry points (`run_cli.py`, `run_web.py`):
```python
import logging
logging.basicConfig(
    level=logging.WARNING,  # INFO in verbose mode
    format='%(name)s: %(message)s'
)
```

## Priority 4: Path Management

### Problem
Fragile relative path construction in `config.py`:
```python
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gutagent.db")
```

### Solution
Create `gutagent/paths.py`:

```python
# gutagent/paths.py
import os
from pathlib import Path

# Project root (parent of gutagent package)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Data directory
DATA_DIR = PROJECT_ROOT / "data"

# Specific paths
DB_PATH = DATA_DIR / "gutagent.db"
PROFILE_PATH = DATA_DIR / "profile.json"
PROFILE_TEMPLATE_PATH = DATA_DIR / "profile_template.json"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)
```

## Priority 5: Test Coverage

### Current Coverage
- ✅ `db/models.py` — well tested
- ✅ `tools/registry.py` — well tested  
- ✅ `profile.py` — well tested
- ❌ `agent.py` — no tests
- ❌ `llm/*` — no tests
- ❌ `api/server.py` — no tests
- ❌ `prompts/system.py` — no tests

### Tests to Add

**Agent integration tests** (`tests/test_agent.py`):
```python
def test_agent_logs_meal(mock_llm):
    """Agent should execute log_meal tool and return confirmation."""
    
def test_agent_handles_follow_up(mock_llm):
    """Agent should use last_exchange for follow-up context."""
    
def test_agent_correction_flow(mock_llm):
    """Agent should use recent_logs for 'change that' corrections."""
```

**API endpoint tests** (`tests/test_api.py`):
```python
from fastapi.testclient import TestClient

def test_chat_endpoint_requires_auth():
    """POST /api/chat should require authentication when configured."""

def test_chat_endpoint_streams_response():
    """POST /api/chat should return SSE stream."""
```

**System prompt tests** (`tests/test_prompts.py`):
```python
def test_dynamic_context_includes_recent_meals():
    """Dynamic context should include meals from last 3 days."""

def test_nutrition_alerts_appear_in_context():
    """Nutrition alerts should appear when deficiencies exist."""
```

## Lower Priority

### Web Streaming Abstraction
Currently `server.py` uses Claude SDK directly for streaming. To support other providers:

1. Implement `chat_stream()` in each provider
2. Create async generator wrapper
3. Use provider abstraction in `server.py`

This is significant work. Acceptable to leave Claude-only for now and document it.

### Connection Pooling
Current pattern opens/closes connection per operation. For a personal tool with low concurrency, this is fine. If scaling to multiple users, consider:
- `sqlite3` connection pool
- Or migrate to async with `aiosqlite`

### Offline Queue
For web UI to work offline:
1. Service worker already caches static assets
2. Need: IndexedDB queue for pending messages
3. Sync on reconnect

This is a nice-to-have, not essential.

---

## Implementation Order

1. **Extract `core.py`** — 2 hours, immediate benefit
2. **Add logging** — 30 minutes, helps debugging
3. **Create `paths.py`** — 30 minutes, cleaner imports
4. **Split `models.py`** — 3 hours, better organization
5. **Add agent tests** — 2 hours, catches regressions
6. **Add API tests** — 1 hour, endpoint coverage

Total: ~9 hours of focused work.
