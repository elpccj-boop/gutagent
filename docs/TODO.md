# GutAgent TODO

## To Do
- [ ] Web streaming LLM abstraction (currently hardcoded to Claude)
- [ ] Setup wizard for new users
- [ ] Offline queue for web UI
- [ ] Permanent URL (purchase domain for Cloudflare)
- [ ] Reduce tool definitions size (13.5K chars, 17 tools)

## Testing

Run tests before committing changes:

```bash
pytest tests/test_gutagent.py -v
```

**What's covered:**

| File | Tested | Notes |
|------|--------|-------|
| `models.py` | ✅ | All database functions |
| `registry.py` | ✅ | All handlers via `execute_tool()` |
| `profile.py` | ✅ | load/save/update profile |
| `config.py` | ❌ | Static tool definitions |
| `system.py` | ❌ | Static prompt text |
| `context.py` | ❌ | Builds API context |

**When to run tests:**
- After editing `models.py` — run all tests
- After editing `registry.py` — run `TestRegistry` class
- After editing `profile.py` — run `TestProfile` class

## Done
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
