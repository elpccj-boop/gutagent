# GutAgent Architecture Comparison: CLI vs Web vs Mobile

## Overview

| Aspect | CLI (`agent.py`) | Web (`server.py`) | Mobile (`mobile.py`) |
|--------|------------------|-------------------|----------------------|
| **Data Location** | Local SQLite | Local SQLite | Phone SQLite |
| **Tool Execution** | Local (Python) | Local (Python) | Local (Dart on phone) |
| **LLM Call** | Direct API | Direct API | Via server proxy |
| **Agent Loop** | In `agent.py` | In `server.py` | In Dart `agent_service.dart` |
| **Streaming** | Yes (to terminal) | Yes (SSE to browser) | Yes (SSE, blocking also available) |

## Architecture Diagrams

### CLI
```
User → agent.py → LLM Provider → Tools (local) → SQLite (local)
         ↑                            ↓
         └────────── loop ────────────┘
```

### Web
```
Browser → server.py (FastAPI) → LLM Provider → Tools (local) → SQLite (local)
              ↑                                      ↓
              └──────────────── loop ────────────────┘
```

### Mobile
```
Flutter App → mobile.py (FastAPI) → LLM Provider
    ↑              ↓
    │         (returns tool_use blocks)
    │              ↓
    └── Tools (Dart, local) → SQLite (on phone)
              ↓
         (sends tool_results)
              ↓
         mobile.py → LLM Provider
              ↓
         (loop continues until end_turn)
```

## Key Differences

### 1. Agent Loop Location

| Version | Agent Loop | Tool Execution |
|---------|-----------|----------------|
| CLI | `agent.py` (Python) | `tools/registry.py` (Python) |
| Web | `server.py` (Python) | `tools/registry.py` (Python) |
| Mobile | `agent_service.dart` (Dart) | `tool_executor.dart` (Dart) |

**Impact:** Mobile's agent loop is in the app, NOT the server. The server is just an LLM proxy.

### 2. System Prompt Handling

| Version | Three-Tier Caching |
|---------|-------------------|
| CLI | ✅ Claude: 3-tuple `(static, patient_data, turn_context)` |
| Web | ✅ Same as CLI |
| Mobile | ✅ Claude: 3-tuple, Gemini/OpenAI: dynamic context in user message |

### 3. Caching by Provider

#### Claude

| Version | Implementation |
|---------|---------------|
| CLI | `cache_control` markers on static + patient_data blocks |
| Web | Same as CLI |
| Mobile | ✅ Same — `cached_system` list with markers, empty blocks skipped |

#### Gemini

| Version | Implementation |
|---------|---------------|
| CLI | `client.caches.create()` with module-level `_gemini_cache_store` |
| Web | Same (uses same provider) |
| Mobile | ✅ Same — explicit cache creation with `_get_or_create_gemini_cache()` |

#### OpenAI

| Version | Implementation |
|---------|---------------|
| CLI | Automatic prefix caching (system prompt first) |
| Web | Same |
| Mobile | ✅ Same + reports `cache_read_input_tokens` |

### 4. Dynamic Context Handling

#### CLI/Web for Gemini/OpenAI
```python
# Move patient_data + turn_context to user message
dynamic_context = f"{patient_data}\n\n{turn_context}"
content = f"[Current Context]\n{dynamic_context}\n\n[User Message]\n{content}"
```

#### Mobile
Server-side `_prepend_dynamic_context()` does the same for Gemini/OpenAI:
```python
def _prepend_dynamic_context(messages, patient_data, turn_context):
    # Prepend to first user message content
    dynamic_context = f"{patient_data}\n\n{turn_context}"
    content = f"[Current Context]\n{dynamic_context}\n\n[User Message]\n{content}"
```

Claude receives all 3 parts separately for proper cache breakpoints.

### 5. Tool Call Handling

| Version | Multi-Tool Support |
|---------|-------------------|
| CLI | ✅ `response.get_tool_calls()` returns list, loops all |
| Web | ✅ Same pattern |
| Mobile Server | ✅ Returns ALL `tool_use` blocks in response |
| Mobile App | ✅ `response.toolUses` list, loops all in `agent_service.dart` |

### 6. Message History

| Version | Pattern | Tokens |
|---------|---------|--------|
| CLI | `last_exchange` only (prev Q&A) | ~3 messages max |
| Web | `last_exchange` via session store | ~3 messages max |
| Mobile | ✅ `_lastExchange` pattern | ~3 messages max |

### 7. Session State

| Version | Storage | Persists |
|---------|---------|----------|
| CLI | In-memory dict | Process lifetime |
| Web | `sessions` dict (keyed by session_id) | Process lifetime |
| Mobile | Dart `_recentLogs` + `_lastExchange` | App lifetime |

### 8. Streaming Support

| Version | Blocking | Streaming |
|---------|----------|-----------|
| CLI | — | ✅ Native to terminal |
| Web | — | ✅ SSE to browser |
| Mobile | ✅ `POST /chat` | ✅ `POST /chat/stream` (SSE) |

Streaming events:
- `{"type": "text", "content": "..."}` — Text chunk
- `{"type": "tool_start", "name": "...", "id": "..."}` — Tool starting
- `{"type": "tool_input", "content": "..."}` — Tool input JSON chunk  
- `{"type": "tool_use", "id": "...", "name": "...", "input": {...}}` — Complete tool
- `{"type": "usage", "input_tokens": N, ...}` — Token usage
- `{"type": "done", "stop_reason": "..."}` — Stream complete

## What Mobile.py Mirrors from CLI/Web

### ✅ Fully Implemented
1. Claude three-tier caching with `cache_control` markers
2. Gemini explicit caching with `client.caches.create()`
3. OpenAI automatic prefix caching
4. Multi-tool response handling (all tools returned)
5. Token usage reporting normalized to Claude semantics
6. Dynamic context prepending for Gemini/OpenAI
7. Streaming support via SSE
8. Empty system/tools handling (skip vs error)

### ⚠️ Different by Design
1. **No agent loop** — server is just LLM proxy, app has the loop
2. **No tool execution** — tools run on phone, server just forwards
3. **No profile/DB access** — all health data stays on phone
4. **Auth via JWT** — not HTTP Basic (multi-user support)

## Mobile.py Structure

```python
@app.post("/chat")
async def chat(request: ChatRequest):
    # request contains: messages, system, patient_data, turn_context, tools
    
    if provider == "claude":
        # Three-tier caching: pass all 3 parts separately
        return await _call_claude(
            messages=request.messages,
            system=request.system,           # Cached
            patient_data=request.patient_data, # Cached (separate breakpoint)
            turn_context=request.turn_context, # Not cached
            tools=request.tools
        )
    else:
        # Gemini/OpenAI: cache system only, move dynamic to user message
        messages = _prepend_dynamic_context(
            request.messages, 
            request.patient_data, 
            request.turn_context
        )
        return await _call_gemini_or_openai(
            messages=messages,
            system=request.system,  # Cached (Gemini explicit, OpenAI automatic)
            tools=request.tools
        )

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    # Same routing logic, but yields SSE events
    return StreamingResponse(_stream_chat(...), media_type="text/event-stream")
```

## Summary: Mobile.py Parity with CLI/Web

| Feature | CLI/Web | Mobile |
|---------|---------|--------|
| Claude 3-tier cache | ✅ | ✅ |
| Gemini explicit cache | ✅ | ✅ |
| OpenAI auto cache | ✅ | ✅ |
| Dynamic context in user msg | ✅ | ✅ |
| Multi-tool returns | ✅ | ✅ |
| Normalized token usage | ✅ | ✅ |
| Streaming | ✅ | ✅ |
| Server logging | Basic | ✅ Enhanced (question, iteration, totals) |

## Server Logging

Mobile.py provides detailed request logging:

```
============================================================
CHAT REQUEST from user@example.com
  Question: How's my nutrition?
  Iteration: 1 | Messages: 1 | Tools: 18
  System: 2624 | Patient: 710 | Turn: 32 chars
============================================================
   → gemini-2.5-flash
      → Text: Your nutrition over the last 3 days...
   TOTAL: in=494 out=141 | cache: 3675 read
```

Multi-iteration example:
```
============================================================
CHAT REQUEST from user@example.com
  Question: log eggs for breakfast
  Iteration: 1 | Messages: 1 | Tools: 18
============================================================
   → gemini-2.5-flash
      → Tool: log_meal
============================================================
CHAT REQUEST from user@example.com
  Question: log eggs for breakfast
  Iteration: 2 | Messages: 3 | Tools: 18
============================================================
   → gemini-2.5-flash
      → Text: Logged eggs for breakfast...
   TOTAL (2 iterations): in=1100 out=150 | cache: 7350 read
```
