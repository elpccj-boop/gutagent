# GutAgent TODO

## Now (Technical Debt)

- [ ] Add tests for `system.py` and `llm/*`

## Next (Features)

- [ ] Setup wizard for new users

## Later (Nice to Have)

- [ ] Offline queue for web UI
- [ ] Permanent URL (purchase domain for Cloudflare)
- [ ] Connection Pooling

## Backlog

- [ ] Confirm query_log defaults for #days to go back
- [ ] Add API endpoint tests
- [ ] Add util for transferring / syncing data across DBs.

## Done
- [x] Normalize token usage reporting across all providers (Claude semantics)
- [x] Add context caching for Gemini/OpenAI provider (usage reporting)
- [x] Add configurable cache TTL for Claude (5min default, 1h option)
- [x] Add web streaming for Gemini/OpenAI providers
- [x] Add recipes to recent logs so they can be corrected
- [x] Same symptom should not be logged repeatedly while chatting
- [x] Verify labs are logged without test date errors
- [x] Add integration tests for `agent.py`
- [x] Add token usage reporting for Gemini provider
- [x] Add timestamp to CLI and Web display (helps debug cache expiry)
- [x] Fix vitals context bug ('str' object has no attribute 'get')
- [x] Extract shared code from `agent.py` and `server.py` into `core.py`
- [x] Split `models.py` into focused modules (connection, common, logs, recipes, nutrition)
- [x] Add error logging in `prompts/system.py`
- [x] Create `paths.py` for centralized path management
- [x] Move `profile_template.json` to `gutagent/` (data/ now gitignored)
- [x] Consolidate test imports (100 scattered → 4 at top)
- [x] Set Vitamin A and D units to IU
- [x] Reduced static prompt to 6215 tokens
- [x] Reduced dynamic tokens by replacing conv history with last exchange and recent logs 
- [x] Added lab test logging and editing
- [x] Recipe system with per-serving nutrition storage
- [x] Backfill 43 meals with complete macro + micronutrient data
- [x] Fix display rounding for small nutrient values (omega-3, B12, iron, zinc)
- [x] Emphasize recipe matching in system prompt
- [x] Fixed meal description vs meal_type issue ("pakoda for snack" in description)
- [x] Removed conversation history (each question is independent now)
- [x] Added recent_logs + last_exchange for corrections and follow-ups
- [x] Compacted tool results (vitals, meals, nutrition, labs, meds, symptoms)
- [x] Fixed DB schema (vitals, sleep, exercise had broken id columns)
- [x] Renamed medication_events → medications
- [x] Added meal timestamp instructions (breakfast=08:00, lunch=12:30, etc.)
- [x] Added BP format hint (123/85/82 = sys/dia/hr)
- [x] Added meal content update instruction (delete + re-log)
- [x] Removed RAG placeholder (not needed — LLM knowledge sufficient)
- [x] Removed Groq and Ollama from docs (unreliable)
- [x] Rewrote ARCHITECTURE.md (clean, focused version)
