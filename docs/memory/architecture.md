# Architecture Memory

## Project: Qwen Council - Multi-Agent Code Review System

### Stack
- **Backend:** Python (FastAPI) + SQLAlchemy + async sessions
- **Agents:** 5 specialized agents (Architecture, Quality, Security, Performance, UX) + Council orchestrator
- **LLM:** Alibaba Qwen via OpenAI SDK v2.x (compatible API)
- **Frontend:** Next.js + TypeScript
- **Infra:** Docker Compose + Alibaba ECS

### Key Architectural Decisions
1. **OpenAI SDK v2.x compatibility** — Uses `AsyncOpenAI` with custom base URL for Qwen API
2. **Module-level patching** for tests — Pragmatic over pure; patches `AsyncOpenAI` at module level in `test_agents.py`
3. **Async session factory** — Returns sessions with mocked `commit()`, `execute()`, etc.
4. **Impact normalization** — `_normalize_impact()` outputs Spanish: `Crítico`, `Alto`, `Medio`, `Bajo`

### Test Infrastructure
- 101 tests all passing
- conftest.py provides: `mock_async_session_factory`, `client`, `mock_db_session`
- test_agents.py uses module-level `patcher` for agents that create `AsyncOpenAI` directly
