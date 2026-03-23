# GutAgent TODO

## Now (Technical Debt)

- [ ] Add integration tests for `agent.py`
- [ ] Add API endpoint tests

## Next (Features)

- [ ] Setup wizard for new users
- [ ] Web streaming for Gemini/OpenAI (currently Claude-only)

## Later (Nice to Have)

- [ ] Offline queue for web UI
- [ ] Permanent URL (purchase domain for Cloudflare)

## Backlog (Unverified)

- [ ] Add recipes to recent logs so they can be corrected
- [ ] Verify labs are logged without test date errors
- [ ] Same symptom should not be logged repeatedly while chatting
- [ ] Confirm query_log defaults for #days to go back


## Done
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
