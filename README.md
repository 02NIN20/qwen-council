# Multi-Agent Council

**Track 3: Agent Society** — [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Track 3 Criteria Mapping

| Criterion | How Multi-Agent Council Meets It | Evidence |
|:----------|:--------------------------|:---------|
| **Multiple agents with distinct capabilities** | 6 role-based core agents + 15 sub-agents, each with unique prompts, specialisations, and tools | `backend/agents/core/` — 6 agents; `backend/agents/subagents/` — 15 sub-agents |
| **Task decomposition & role assignment** | Coordinator plans review, delegates to Analyst/Architect/Engineer/Critic/Researcher. Questions classified into 8 categories and routed to 1-3 relevant agents | `_classify_question()` + `_route_question()` in `backend/main.py`; `TaskPlanner` sub-agent |
| **Dialogue & negotiation** | 3 debate rounds (individual -> cross-debate -> refinement) with early-exit when no new findings; budget-aware execution stops when exhausted | `backend/council/orchestrator.py` — round execution, early exit, budget tracking |
| **Quantifiable improvement** | Multi-agent finds **2.36x more findings** than single-agent (33 vs 14), with **85.7% coverage overlap** + 19 unique findings | `benchmark_results.md` — combined results across 3 apps |
| **Sub-agents & tools** | Each core agent delegates to specialised sub-agents (TaskPlanner, SecurityAuditor, CodeWriter, etc.) and uses tools (CodeSearch, StaticAnalysis, etc.) | `backend/agents/subagents/` (15 files), `backend/agents/tools/` (4 files) |
| **Proactive behaviour** | Agents can initiate actions: escalate critical findings, propose refactors, research topics autonomously | `implement_fix()`, `escalate_finding()`, `research_topic()` methods on core agents |

---

## What is Multi-Agent Council?

Multi-Agent Council is a **multi-agent collaboration system** where 6 role-based AI agents with **15 specialised sub-agents** and **4 tools** collaborate to perform code review and answer questions.

### Key Innovation: Agent Society Architecture

Unlike traditional multi-agent systems where each agent is a "personality", Multi-Agent Council implements a **functional society** of agents:

| Agent | Role | Sub-agents | Tools | Proactive Actions |
|:------|:-----|:-----------|:------|:------------------|
| **Coordinator** | Orchestrates workflow, delegates tasks | TaskPlanner, PriorityRouter | CodeSearch, StaticAnalysis, DependencyAnalysis, DocLookup | Plan review, escalate findings, synthesize responses |
| **Analyst** | Examines code, detects patterns, analyses complexity | StaticAnalyzer, PatternDetector, ComplexityAnalyzer | CodeSearch, StaticAnalysis | Detect patterns, analyse complexity |
| **Architect** | Designs solutions, plans structure, maps dependencies | DesignPatternMatcher, DependencyMapper | DependencyAnalysis, DocLookup | Suggest architecture, plan refactors |
| **Engineer** | Implements fixes, writes code, optimises | CodeWriter, Refactorer, Optimizer | CodeSearch | Implement fix, optimise code |
| **Critic** | Reviews, validates, finds bugs, audits security | SecurityAuditor, PerformanceReviewer, StyleChecker | StaticAnalysis, CodeSearch | Security audit, performance review |
| **Researcher** | Documents, researches best practices, explains code | DocGenerator, BestPracticeLookup | DocLookup | Research topic, document code |

### Communication Protocol

Each agent message follows the **Inverted Pyramid** format:

```
FINDING: SQL injection vulnerability at user input handling
... Detail: src/app.py line 45: cursor.execute(f"SELECT * FROM users WHERE id = {user_input}") (CWE-89)
... Impact: Critical
... Proposal: Use parameterised queries
```

In rounds 2+, agents apply **Given-New** cross-referencing:

```
FINDING: Agreeing with Critic on SQL injection at line 45, I found the same pattern at line 78
... Detail: src/app.py line 78: same f-string pattern in delete_user() (CWE-89)
... Impact: Critical
... Proposal: Create a safe_query() helper
```

---

## Architecture

![Multi-Agent Council Architecture Diagram](docs/architecture_diagram.png)

*Generated with Python (matplotlib) — see `docs/generate_diagram.py`*

---

## Benchmark Results

### Combined (3 applications, 548 lines)

| Metric | Single-Agent | Multi-Agent | Change |
|:-------|:-------------|:------------|:-------|
| Total findings | 14 | 33 | **+135.7%** |
| Categories covered | 4/6 | 6/6 | **+50.0%** |
| Recall | 92.9% | 66.1% | -26.8% |
| Precision | 54.2% | 41.0% | -13.2% |
| Avg severity score (1-4) | 3.0 | 3.2 | **+6.7%** |

**Overlap:** 85.7% of single-agent findings ALSO found by multi-agent.  
**Unique to multi-agent:** 19 findings (multi-agent covers 6/6 categories vs 4/6).  
**Unique to single-agent:** 2 findings missed by specialists.

**Conclusion:** Multi-agent council finds **2.36x more findings**, covers **all 6 categories**, and detects higher-severity issues. Use `light` mode (3 agents, 2 rounds) for quick scans; `full` mode (6 agents, 3 rounds) for deep reviews.

For a detailed breakdown, see `benchmark_results.md` or the in-app Benchmark Dashboard (`[B]` button in sidebar).

---

## Memory Architecture (3 Levels + Forgetting Curve)

| Level | Storage | Content | Lifecycle |
|:------|:--------|:--------|:----------|
| Working Memory | Python dict (volatile) | Current code, round findings, debate state | Session start → end |
| Episodic Memory | PostgreSQL | Complete sessions: code, findings, votes, decisions | Last 20 active sessions, forgetting curve (-0.1/day) |
| Semantic Memory | PostgreSQL + pgvector | User preferences, learned rules, consolidated patterns | Permanent, embeddings via Qwen API |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker + Docker Compose (optional, for production)
- Qwen Cloud API key ([get one free](https://modelstudio.console.alibabacloud.com))

### 1. Clone & Setup

```bash
git clone https://github.com/02NIN20/multiagent-council.git
cd multiagent-council

# Backend
pip install -r backend/requirements.txt
cp .env.example .env
# Edit .env and set your llm_api_key

# Frontend
cd frontend
npm install
```

### 2. Run Locally (Development)

```bash
# Terminal 1: Backend (from project root)
PYTHONPATH=. uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open http://localhost:5173

### 3. Run with Docker (Production)

```bash
cp .env.example .env
nano .env   # Set your llm_api_key
docker compose up --build -d
```

---

## API Endpoints

All endpoints available under both `/api/v1/` (versioned) and `/api/` (legacy) prefixes.

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/v1/review` | Submit code for multi-agent council review (sync, supports files + images) |
| `POST` | `/api/v1/review/stream` | **Stream** review progress via SSE (round_start, agent_start, agent_complete, early_exit, budget_exhausted, synthesis_complete, complete) |
| `POST` | `/api/v1/chat` | Multi-agent chat (message + optional files + images) |
| `GET` | `/api/v1/sessions` | List past sessions (review + chat) |
| `GET` | `/api/v1/sessions/{id}` | Get session details and report |
| `DELETE` | `/api/v1/sessions/{id}` | Delete a session |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/diagnostics` | Last LLM errors |
| `POST` | `/api/v1/diagnostics/clear` | Clear error log |

### Review Modes

| Mode | Agents | Rounds | Token Usage | Use Case |
|:-----|:-------|:-------|:------------|:---------|
| `full` (default) | 6 agents | 3 rounds | ~100% | Thorough review, max coverage |
| `light` | 3 agents (critic, analyst, architect) | 2 rounds | ~40% | Quick scan, budget-conscious |

### POST /api/v1/review/stream

```json
{
  "code": "def hello():\n    return 1",
  "files": [
    { "filename": "main.py", "content": "def hello():\n    return 1", "language": "python" }
  ],
  "images": [
    { "filename": "diagram.png", "content": "<base64>", "mime_type": "image/png" }
  ],
  "instruction": "Focus on security vulnerabilities",
  "mode": "full",
  "session_id": "ses-abc123def456"
}
```

**SSE Events:** `round_start`, `agent_start`, `agent_complete`, `round_complete`, `early_exit`, `budget_exhausted`, `synthesis_complete`, `complete`, `error`

### POST /api/v1/chat

```json
{
  "message": "What is SOLID?",
  "session_id": "chat-abc123"
}
```

---

## Frontend Architecture

```
frontend/
  src/
    main.tsx              # React entry point
    App.tsx               # Root: state-driven view switching
    index.css             # Tailwind + retro theme
    api/
      council.ts          # REST API client (/api/v1/*)
      streamReview.ts     # SSE stream parser + dispatcher
    components/
      ChatView.tsx        # Message list + follow-up
      ChatInput.tsx       # Text input + file/image upload
      ChatMessage.tsx     # Message renderer (user, agent, finding, report, answer)
      Sidebar.tsx         # Session list + filter + new session
      LiveCouncilStatus.tsx  # Live SSE streaming status UI
      BenchmarkDashboard.tsx # Multi vs single-agent comparison charts
      ErrorBoundary.tsx   # React error boundary
    data/
      benchmarkData.ts    # Embedded benchmark results
    types/
      index.ts            # TypeScript types (Finding, Report, TokenUsage, ...)
```

The frontend uses **no router library** — view switching is state-driven:
- `isLoading` → `LiveCouncilStatus` (SSE stream)
- `showBenchmark` → `BenchmarkDashboard`
- Default → `ChatView` (messages + input)

---

## CLI Tool

```bash
# Setup (first time)
python3 cli.py setup --url http://localhost:8000

# Code review
python3 cli.py review main.py
python3 cli.py review main.py utils.py --instruction "Focus on security"

# Chat
python3 cli.py chat "What is dependency injection?"
python3 cli.py chat "Why did you flag that SQL injection?" --session chat-abc123

# List sessions
python3 cli.py sessions
```

---

## MCP Server

Expose the Agent Society as tools for **OpenCode**, **Claude Desktop**, **Cursor**, etc.

### Setup (1 minute)

```bash
# 1. Add to ~/.config/opencode/opencode.jsonc:
{
  "mcp": {
    "multiagent-council": {
      "type": "local",
      "command": ["bash", "/path/to/multiagent-council/run_mcp.sh"],
      "enabled": true
    }
  }
}

# 2. Restart OpenCode — 7 tools available:
#    chat, analyze_file, review_code, generate_code,
#    implement_fix, list_sessions, get_session
```

See `MCP_SETUP.md` for detailed instructions.

### Tools

| Tool | Description |
|:-----|:------------|
| `chat(message)` | Ask the 6-agent society any question |
| `analyze_file(filename, content, question)` | Analyze a code or text file |
| `review_code(code, instruction, mode)` | Multi-agent code review (light/full) |
| `generate_code(specification, language)` | **Generate code** from spec |
| `implement_fix(code, issue)` | **Fix code** issues |
| `list_sessions(limit)` | List past sessions |
| `get_session(session_id)` | Get session details |

### Run locally (without MCP)

```bash
QWEN_COUNCIL_API_URL=http://localhost:8000 python3 -m backend.mcp_server
```

---

## API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI spec: `http://localhost:8000/openapi.json`

---

## Tests

```bash
# Run all 138 tests
python3 -m pytest backend/tests/ -v

# Run specific test file
python3 -m pytest backend/tests/test_agents.py -v

# Run with coverage
pip install pytest-cov
python3 -m pytest backend/tests/ --cov=backend
```

**Test suite**: 138 tests covering:
- 6 core agents (individual analysis, debate rounds, empty code, sub-agent delegation)
- 17 Agent Society tests (sub-agents, tools, budget, early-exit, failure tolerance)
- API endpoints (health, review, chat, sessions, CORS, content detection)
- Memory system (working, episodic with forgetting curve, semantic with pgvector)
- Council synthesizer (clustering, consensus, formatting)
- Orchestrator (session IDs, round execution, failure handling, budget tracking)
- Content detection (code, math, research, text, markdown)

All tests use mocked LLM calls — no API key needed.

---

## LLM Provider Abstraction

Multi-Agent Council supports swapping the LLM provider without changing agent code:

```python
from backend.llm.provider import LLMProvider, LLMResponse, get_provider, set_provider

# Default: Qwen Cloud DashScope
provider = get_provider()
response = await provider.complete(
    model="qwen-plus-latest",
    messages=[{"role": "user", "content": "Hello"}],
)

# Custom provider (for testing or different LLM)
class MockProvider(LLMProvider):
    async def complete(self, model, messages, **kwargs):
        return LLMResponse(content="Mock response", model=model)

set_provider(MockProvider())
```

Configuration via `.env`:
```env
llm_api_key=sk-your-key
llm_model=qwen-plus-latest
llm_base_url=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
llm_provider=qwen
```

---

## Robustness Features

| Feature | Description |
|:--------|:------------|
| **Rate limit handling** | 3 retries with exponential backoff (1s → 2s → 4s) on 429 errors |
| **Per-agent timeouts** | 120s timeout per agent — a hung agent doesn't block the review |
| **Light mode** | `mode: "light"` uses 3 agents + 2 rounds (~60% fewer tokens) |
| **Token tracking** | Per-agent breakdown + estimated cost in every response |
| **Structured logging** | JSON logs with `X-Request-ID` header for production debugging |
| **API versioning** | `/api/v1/` routes with `/api/` backward compatibility |
| **Image upload** | Upload screenshots/diagrams — routed via content-aware detection to the Analyst/Researcher agents for visual analysis |
| **Sub-agents** | 15 specialised sub-agents for focused analysis tasks |
| **Tools** | CodeSearch, StaticAnalysis, DependencyAnalysis, DocLookup |

---

## Deployment on Alibaba Cloud ECS

```bash
ssh root@your-ecs-ip
git clone https://github.com/02NIN20/multiagent-council.git
cd multiagent-council
cp .env.example .env
nano .env   # Set llm_api_key, llm_base_url, llm_model
sudo bash deploy.sh
```

Available at: **http://47.84.227.185/**

---

## Built for

[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society

---

## License

MIT
