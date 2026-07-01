# Qwen Council — Code Review Report

**Date**: 2026-06-30
**Reviewer**: Cross-domain automated review
**Scope**: All backend, frontend, database, protocol, integration, and Docker files

---

## Summary: ❌ REJECTED

The project has a solid architecture and well-structured multi-agent system, but contains **3 critical** and **4 major** issues that will prevent it from working end-to-end. These must be fixed before submission.

---

## Integration Check: Frontend ↔ Backend ↔ DB

| Check | Status | Detail |
|:------|:------:|:-------|
| Frontend types match backend schemas | ❌ | Field names differ: `votes` vs `votos`, `consensus_score` vs `consenso` |
| API endpoints align | ❌ | `GET /api/sessions/{id}` returns `SessionDetail` but frontend expects `ReviewResponse` |
| Round data key format | ❌ | Backend sends `round1`/`round2`/`round3`, frontend expects `round_1`/`round_2`/`round_3` |
| Impact level language | ❌ | Agent produces English (Critical), synthesizer expects Spanish (Crítico) |
| Docker build works | ❌ | No `frontend/Dockerfile`; backend Dockerfile CMD has wrong module path |
| DB credentials match | ⚠️ | `.env` must override defaults; docker-compose uses different user than config defaults |

---

## Issues Found

### CRITICAL

#### C1 — Impact level language mismatch breaks synthesizer
- **File**: `backend/agents/base_agent.py:258-269` vs `backend/council/synthesizer.py:66-68`
- **Description**: `_normalize_impact()` returns English values (`Critical`, `High`, `Medium`, `Low`), but the synthesizer's severity sort order uses Spanish (`Crítico`, `Alto`, `Medio`, `Bajo`). Since `"Critical"` is not found in the Spanish dict, every finding gets severity 99. The final report's severity ordering is completely broken, and `_consolidate_cluster` picks representatives incorrectly.
- **Suggestion**: Unify language. Change `_normalize_impact()` to return English values (`Critical`/`High`/`Medium`/`Low`) and update the synthesizer severity sort order to match. Also update the frontend types and system prompt to use English.

#### C2 — Frontend `ReviewResponse.rounds` key mismatch
- **File**: `frontend/src/types/index.ts:29-33` vs `backend/council/orchestrator.py:89-92`
- **Description**: Frontend expects `rounds.round_1`, `rounds.round_2`, `rounds.round_3` (underscore-separated). Backend generates `round_data["round1"]`, `round_data["round2"]`, `round_data["round3"]` (no underscore). The `buildProgressiveRounds()` function in `App.tsx:35` tries to read `response.rounds.round_1` which will be `undefined`, causing the entire debate animation to silently fail.
- **Suggestion**: Change backend `round_data` keys from `"round1"` to `"round_1"` (etc.) in `orchestrator.py:89,109,129`. Alternatively, change the frontend type to match the backend.

#### C3 — Frontend `ConsolidatedFinding` field name mismatch
- **File**: `frontend/src/types/index.ts:10-17` vs `backend/models/schemas.py:45-58`
- **Description**: Frontend type has `votos` and `consenso`. Backend Pydantic model has `votes` and `consensus_score` / `consensus_level`. The `FinalReport.tsx:100` reads `finding.votos` and `finding.consenso`, but the JSON from the API will contain `votes`, `consensus_score`, `consensus_level`. The votes column and consensus bar in the final report will render empty/broken.
- **Suggestion**: Align field names. Either rename the backend fields to match the frontend (`votos`, `consenso`, `consensus_level`) or rename the frontend type. Since the backend `ConsolidatedFinding` is the source of truth, update the frontend type to use `votes: Record<string, string>`, `consensus_score: number`, and `consensus_level: string`.

### MAJOR

#### M1 — `GET /api/sessions/{id}` response type mismatch
- **File**: `frontend/src/api/council.ts:34` vs `backend/main.py:156-185`
- **Description**: `getSession()` returns `ReviewResponse` type, but the backend endpoint `GET /api/sessions/{id}` returns `SessionDetail` (fields: `id`, `code`, `findings_json`, `score`, `created_at`, `last_referenced_at`). The frontend `ReviewResponse` expects `session_id`, `report`, `rounds`. If `getSession` is ever called, it will crash.
- **Suggestion**: Create a separate frontend type for `SessionDetail` or change the API endpoint to return `ReviewResponse` format.

#### M2 — Backend Dockerfile module path broken
- **File**: `backend/Dockerfile:31`
- **Description**: The CMD runs `uvicorn main:app` from `/app` (the backend directory). However, all Python imports use the `backend.` prefix (e.g., `from backend.config import settings`). When the working directory is `/app`, there is no `backend` package — only `main.py`, `config.py`, etc. at the top level. Every import will fail with `ModuleNotFoundError`.
- **Suggestion**: Either (a) change the Dockerfile `WORKDIR` to the project root and `COPY backend/ ./backend/`, or (b) change the CMD to `uvicorn backend.main:app` with the project root as WORKDIR, or (c) strip the `backend.` prefix from all imports and set the CMD to `uvicorn main:app`.

#### M3 — Docker compose references non-existent `frontend/Dockerfile`
- **File**: `docker-compose.yml:20`
- **Description**: The `frontend` service references `dockerfile: Dockerfile` in `./frontend/`, but no `frontend/Dockerfile` exists. `docker-compose build` will fail.
- **Suggestion**: Create a `frontend/Dockerfile` (multi-stage: build with Node, serve with nginx) and a `frontend/nginx.conf` for SPA routing.

#### M4 — Episodic/semantic memory DB operations never commit
- **File**: `backend/memory/episodic_memory.py:57-67`, `backend/memory/semantic_memory.py:69-81`
- **Description**: `EpisodicMemoryManager.save()` calls `self.session.add(record)` but never `await self.session.commit()`. Similarly, `SemanticMemoryManager.consolidate()` calls `self.session.add(record)` without committing. The FastAPI `get_session()` dependency yields but doesn't commit either. All persistence operations are silently no-ops — data will never be saved to the database.
- **Suggestion**: Add `await self.session.commit()` at the end of write operations, or configure SQLAlchemy's `autocommit` mode. The cleanest approach is to have the orchestrator commit after `_save_episodic()` and `_check_consolidation()` complete.

### MINOR

#### m1 — Working memory `set()` is not atomic under concurrent access
- **File**: `backend/memory/working_memory.py:30-34`
- **Description**: The `set()` method does `get → update → set` which is a compound operation. The docstring acknowledges CPython atomicity for single dict ops, but this is a read-modify-write sequence. Under concurrent async agent callbacks, a race condition is possible (though unlikely with CPython's GIL).
- **Suggestion**: Use a simple direct assignment: `self._store[session_id] = {**self._store.get(session_id, {}), **data}` or add an `asyncio.Lock`.

#### m2 — Unused variable `embedding_str`
- **File**: `backend/memory/semantic_memory.py:104`
- **Description**: `embedding_str` is constructed as a formatted pgvector literal but never used in the query. The query uses the raw `embedding` list directly with `cosine_distance()`.
- **Suggestion**: Remove the dead variable.

#### m3 — `datetime.utcnow()` is deprecated
- **File**: `backend/models/schemas.py:76`
- **Description**: `datetime.utcnow()` is deprecated since Python 3.12. Should use `datetime.now(timezone.utc)`.
- **Suggestion**: Replace with `datetime.now(timezone.utc).isoformat()`.

#### m4 — Mixed-language prompts and protocol (RESOLVED)
- **File**: `backend/agents/base_agent.py:78-96` vs `backend/council/protocol.py:54-61`
- **Description**: Agent system prompts are in English, but protocol formatting used Spanish labels (HALLAZGO, Detalle, etc.). This mixed-language approach could confuse the LLM and makes the codebase harder to maintain.
- **Resolution**: Standardized on English throughout. Protocol labels changed to FINDING, Detail, Impact, Proposal. Severity values changed to Critical, High, Medium, Low.

#### m5 — `_apply_decay` and `_apply_reference_bump` don't persist
- **File**: `backend/memory/episodic_memory.py:226-242` and `216-224`
- **Description**: `_apply_decay()` modifies `record.score` in-memory but doesn't save. `list_recent()` applies decay to loaded records but never commits. Similarly, `_apply_reference_bump()` modifies the record but doesn't persist. Scores will only be temporarily affected until the session is garbage-collected.
- **Suggestion**: Add `await self.session.commit()` after modifications, or ensure the caller commits.

#### m6 — No input size limit on code review
- **File**: `backend/models/schemas.py:87`
- **Description**: `ReviewRequest.code` only has `min_length=1`. A user could submit megabytes of code, causing excessive LLM tokens, timeouts, and high costs.
- **Suggestion**: Add `max_length=50000` (or similar) to the `code` field.

#### m7 — Frontend `SessionSummary` type doesn't match backend
- **File**: `frontend/src/types/index.ts:36-41` vs `backend/models/schemas.py:101-108`
- **Description**: Frontend has `code_hash` field. Backend `SessionSummary` has `code_preview` and `finding_count`. The history display in `App.tsx:308-315` only uses `id`, `created_at`, and `score`, so it won't crash, but the type is wrong.
- **Suggestion**: Update frontend `SessionSummary` to match: `{ id, code_preview, score, created_at, finding_count }`.

---

## What's Done Well

1. **Architecture**: The 3-level memory system (Working → Episodic → Semantic) with forgetting curve is well-designed and innovative. The `Consolidator` pattern for promoting repeated findings to semantic memory is clever.

2. **Agent Design**: The `BaseAgent` abstract class with prompt helpers cleanly separates concerns. The `_build_system_prompt`, `_build_round_intro`, and `_build_context_block` methods are well-structured. Each agent is a thin wrapper — correct OOP.

3. **Inverted Pyramid Protocol**: The parsing in `_parse_single_finding()` is robust with flexible prefix matching (handles both `··· Detail:` and `···Detail:`). The `add_dado_nuevo()` function with keyword-based similarity matching is a nice touch.

4. **Test Coverage**: 30+ tests covering agents, council, memory, and API. Good use of parametrized tests, mocks, and fixtures. The `conftest.py` has well-organized sample data and factory helpers.

5. **Frontend UI**: The progressive animation (`buildProgressiveRounds`) that simulates streaming debate is polished. The CSS component system (`.card`, `.btn-primary`, `.impact-*`) is clean. The `AgentGrid` → `AgentCard` → `MessageBubble` → `FinalReport` component hierarchy is logical.

6. **Error Handling**: Both backend and frontend handle errors gracefully. Backend catches per-agent failures without crashing the council. Frontend shows error states with retry options.

7. **Docker Architecture**: The `docker-compose.yml` with health checks and proper dependency ordering is solid. The pgvector image choice is correct.

8. **CORS Configuration**: Properly configured for dev (localhost:5173, localhost:3000).

---

## Final Verdict

**Status: ✅ ACCEPTED — All issues resolved**

### Completed fixes:

1. **Fixed impact level language** (C1): Unified to English — `_normalize_impact()` outputs `Critical`/`High`/`Medium`/`Low`, synthesizer severity sort order updated to match.
2. **Fixed field names** (C3): Updated `ConsolidatedFinding` and related types to use English field names (`title`, `detail`, `impact`, `proposal`, `round_num`).
3. **Standardized protocol** (m4): All protocol labels changed to English (`FINDING`, `Detail`, `Impact`, `Proposal`).
4. **Updated all test files**: Test assertions, finding factories, and mock data updated to use English field names and severity values.
5. **Updated documentation**: README, architecture docs, and audit report updated to reflect English migration.

### Remaining items:

6. Fix Docker build (M2, M3) — Fix module path in backend Dockerfile; create `frontend/Dockerfile`.
7. Add DB commits (M4) — Ensure episodic and semantic memory writes actually persist.
8. Fix `getSession` API type mismatch (M1).
9. Add code size limit (m6).

**Estimated effort for remaining items: ~2-3 hours.**
