# Architecture Memory

## Project: Qwen Council - Multi-Agent Code Review System

### Stack
- **Backend:** Python (FastAPI) + SQLAlchemy + async sessions
- **Agents:** 6 specialized agents (Security, Architecture, Quality, Performance, UX, Vision)
- **LLM:** qwen3-coder-plus via dashscope API (OpenAI SDK v2.x compatible)
- **Frontend:** React + TypeScript + Vite
- **Infra:** Docker Compose + nginx + Alibaba ECS
- **SSE:** Real-time streaming via fetch + ReadableStream

### Core Architecture
- **Two-layer design:** Generic multi-agent framework + code review demonstration
- **Given-New protocol:** Inverted Pyramid format for agent communication
- **3 debate rounds:** analysis → cross-debate → refinement
- **Optional Round 4:** negotiation for low-consensus findings

### Key Components
- `backend/orchestrator.py`: Main orchestrator with asyncio.wait_for per agent
- `backend/synthesizer.py`: Merges agent findings into final report
- `backend/benchmark/`: Single-agent vs multi-agent comparison system
- `frontend/LiveCouncilStatus.tsx`: Real-time progress UI
- `frontend/streamReview.ts`: SSE consumer

### Endpoints
- `POST /api/review`: Standard review (returns Finding[])
- `POST /api/review/stream`: SSE streaming with event types

### SSE Event Types
round_start, agent_start, agent_complete, round_complete, synthesis_complete, negotiation_start, negotiation_complete, complete, error

### Finding Model
- title (was hallazgo)
- detail (was detalle)
- impact (was impacto)
- proposal (was propuesta)
- round_num (was ronda)
- severity: Critical/High/Medium/Low

### Test Infrastructure
- 101 tests all passing
- conftest.py provides: mock_async_session_factory, client, mock_db_session
- test_agents.py uses module-level patcher for AsyncOpenAI

### Key Decisions
1. **OpenAI SDK v2.x compatibility** — AsyncOpenAI with custom base URL for Qwen API
2. **Module-level patching** for tests — Pragmatic over pure
3. **Async session factory** — Returns sessions with mocked commit(), execute(), etc.
4. **Impact normalization** — English: Critical, High, Medium, Low
5. **SSE over WebSocket** — Simpler implementation, better compatibility
6. **Negotiation only for disputed findings** — Efficiency over exhaustive debate
7. **All English** — Complete Spanish→English migration for consistency

### Performance Notes
- LLM timeout: 300s (was 120s)
- nginx proxy timeout: 600s (was 130s)
- Multi-agent: ~97s, $0.23 per review
- Single-agent: ~26s, $0.02 per review (10.6x fewer findings)
