# Qwen Council — Multi-Agent Collaboration System

**Track 3: Agent Society** — [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Track 3 Criteria Mapping

| Criterion | How Qwen Council Meets It | Evidence |
|:----------|:--------------------------|:---------|
| **Multiple agents with distinct capabilities** | 6 code review specialists + 8 personality-based agents, each with unique prompts, domains, and expertise | `backend/agents/` — 14 agent files with distinct `role_description` and `domain` |
| **Task decomposition & role assignment** | Questions classified into 8 categories (science, tech, history, philosophy, art, psychology, strategy, general) and routed to 1-3 relevant agents | `_classify_question()` + `_route_question()` in `backend/main.py` |
| **Dialogue & negotiation** | 3 debate rounds (individual → cross-debate → refinement) + Round 4 negotiation that detects severity disagreements and forces consensus | `backend/council/orchestrator.py` — `Round 4: Negotiation` |
| **Quantifiable improvement** | Multi-agent finds **10.6x more findings** than single-agent (127 vs 12), with **100% overlap coverage** + 115 unique findings | `benchmark_results.md` — `vulnerable_app.py` benchmark |

---

## What is Qwen Council?

Qwen Council is a **multi-agent collaboration system** with two modes:

### Mode 1: Code Review (Council)
6 specialised AI agents debate collaboratively to perform code review. Each agent has unique expertise (Security, Architecture, Quality, Performance, UX, Vision) and follows a structured **Inverted Pyramid communication protocol** inspired by cognitive linguistics. After 3 rounds of structured debate + a negotiation round, a final LLM-powered report is generated.

### Mode 2: General Chat (Expert Panel)
8 personality-based agents (inspired by Feynman, Torvalds, Socrates, Harari, Miyazaki, Jung, Sun Tzu, Franklin) answer any question. Each agent has a **strict domain boundary** — they decline out-of-scope questions. A router classifies the question and activates only the 1-3 most relevant agents. Responses are synthesised into a single flowing answer.

---

## Agents

### Code Review Agents (Council Mode)

| Agent | Expertise | Domain |
|:------|:----------|:-------|
| Security | OWASP Top 10, SQLi, XSS, secrets, auth flaws | Vulnerability detection |
| Architecture | SOLID, coupling, scalability, design patterns | System design quality |
| Quality | Code style, dead code, complexity, tests | Code maintainability |
| Performance | N+1 queries, caching, inefficient loops | Runtime efficiency |
| UX | Accessibility, i18n, error messages, contrast | User experience |
| Vision | Screenshot/diagram analysis (qwen-vl-plus) | Visual inspection |

### Chat Agents (Expert Panel Mode)

| Agent | Persona | Domain |
|:------|:--------|:-------|
| Scientist | Richard Feynman | Science, nature, physics |
| Technologist | Linus Torvalds | Technology, engineering, code |
| Philosopher | Socrates | Philosophy, ethics, deep questions |
| Historian | Yuval Noah Harari | History, culture, civilizations |
| Artist | Hayao Miyazaki | Art, literature, music, creativity |
| Psychologist | Carl Jung | Psychology, human mind, archetypes |
| Strategist | Sun Tzu | Strategy, business, decision-making |
| Generalist | Benjamin Franklin | General knowledge, catch-all |

---

## Architecture

```
                    REACT FRONTEND (ChatGPT-style UI)
  Sidebar (sessions) | Chat messages | File upload | Follow-up Q&A
                             |
                      HTTP (REST API)
                             |
                     FASTAPI BACKEND
   POST /api/v1/review  |  POST /api/v1/chat  |  GET /api/v1/sessions
                             |
           ------------------+------------------
           |                                  |
    COUNCIL ORCHESTRATOR                MEMORY SYSTEM
    Round 1: Individual Analysis       Working (in-memory)
    Round 2: Cross-Debate              Episodic (PostgreSQL)
    Round 3: Final Refinement          Semantic (pgvector)
    Round 4: Negotiation
           |
    LLM SYNTHESIZER (qwen3-coder-plus)
    Executive Summary + Risk Overview +
    Detailed Review + Remediation Roadmap
           |
                     QWEN CLOUD API
  https://dashscope.aliyuncs.com/compatible-mode/v1
  Models: qwen3-coder-plus, qwen-vl-plus, text-embedding-v3
```

---

## Benchmark Results

### vulnerable_app.py (8 lines)

| Metric | Single-Agent | Multi-Agent | Change |
|:-------|:-------------|:------------|:-------|
| Total findings | 12 | 127 | **+958.3%** |
| Categories covered | 6/6 | 6/6 | 100% overlap |
| Unique findings | 0 | 115 | +115 |
| Coverage overlap | — | 100% | All single-agent findings preserved |

### ambiguous_code.py (13 lines)

| Metric | Single-Agent | Multi-Agent | Change |
|:-------|:-------------|:------------|:-------|
| Total findings | 10 | 88 | **+780.0%** |
| Categories covered | 4/6 | 6/6 | +50% more categories |
| Avg severity score | 3.1 | 3.3 | +6.5% higher severity |
| Unique findings | 0 | 78 | +78 |

**Conclusion:** Multi-agent system finds **8.8x–10.6x more findings** than a single generalist agent, with **100% coverage overlap** and significantly more unique insights.

---

## Communication Protocol

Each agent message follows the **Inverted Pyramid** format:

```
FINDING: SQL injection vulnerability at user input handling
... Detail: src/app.py line 45: cursor.execute(f"SELECT * FROM users WHERE id = {user_input}") (CWE-89)
... Impact: Critical
... Proposal: Use parameterised queries. BEFORE: cursor.execute(f"SELECT...{user_input}") AFTER: cursor.execute("SELECT...WHERE id = ?", (user_input,))
```

In rounds 2+, agents apply **Given-New** cross-referencing:

```
FINDING: Agreeing with Security on SQL injection at line 45, I found the same pattern at line 78
... Detail: src/app.py line 78: same f-string pattern in delete_user() (CWE-89)
... Impact: Critical
... Proposal: Create a safe_query() helper that always uses parameterisation
```

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
- Qwen Cloud API key

### 1. Clone & Setup

```bash
git clone https://github.com/02NIN20/qwen-council.git
cd qwen-council

# Backend
pip install -r backend/requirements.txt
cp .env.example .env
# Edit .env and set your qwen_api_key

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
nano .env   # Set your qwen_api_key
docker compose up --build -d
```

The frontend will be available on `http://localhost:5173` and the API on `http://localhost:8000`.

---

## API Endpoints

All endpoints are available under both `/api/v1/` (versioned) and `/api/` (legacy) prefixes.

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/v1/review` | Submit code for council review (supports multiple files + images + instructions) |
| `POST` | `/api/v1/review/stream` | Stream review progress via Server-Sent Events |
| `POST` | `/api/v1/chat` | General multi-agent chat (any question, routed to relevant agents) |
| `POST` | `/api/v1/chat/stream` | Stream chat responses via Server-Sent Events |
| `GET` | `/api/v1/sessions` | List past sessions (review + chat) |
| `GET` | `/api/v1/sessions/{id}` | Get session details and findings |
| `DELETE` | `/api/v1/sessions/{id}` | Delete a session |
| `GET` | `/api/v1/memory/patterns` | Get consolidated semantic memory patterns |
| `GET` | `/api/v1/health` | Health check |

### Review Modes

| Mode | Agents | Rounds | Token Usage | Use Case |
|:-----|:-------|:-------|:------------|:---------|
| `full` (default) | 6 agents | 4 rounds (incl. negotiation) | ~100% | Thorough review |
| `light` | 3 agents (security, architecture, quality) | 2 rounds | ~40% | Quick scan, budget-conscious |

### POST /api/v1/review

```json
{
  "files": [
    { "filename": "main.py", "content": "def hello():\n    return 1", "language": "python" }
  ],
  "instruction": "Focus on security vulnerabilities",
  "mode": "full"
}
```

### Response

```json
{
  "session_id": "ses-abc123def456",
  "report": {
    "summary": "The code review identified critical security issues...",
    "findings": [
      {
        "title": "SQL injection vulnerability",
        "impact": "Critical",
        "votes": { "security": "Critical", "architecture": "High" },
        "consensus_level": "High",
        "consensus_score": 1.0
      }
    ],
    "token_usage": {
      "per_agent": { "security": { "input_tokens": 1200, "output_tokens": 800, "total_tokens": 2000 } },
      "total_input_tokens": 7200,
      "total_output_tokens": 4800,
      "total_tokens": 12000,
      "estimated_cost_usd": 0.0864,
      "model": "qwen3-coder-plus"
    }
  }
}
```

### POST /api/v1/chat

```json
{
  "message": "What is SOLID?",
  "session_id": "chat-abc123"
}
```

---

## CLI Tool

Interact with Qwen Council from the terminal:

```bash
# Setup (first time)
python3 cli.py setup --url http://localhost:8000

# Code review
python3 cli.py review main.py
python3 cli.py review main.py utils.py --instruction "Focus on security"

# Chat
python3 cli.py chat "What is the meaning of life?"
python3 cli.py chat "Why did you flag that SQL injection?" --session chat-abc123

# List sessions
python3 cli.py sessions
```

Set `QWEN_COUNCIL_URL` environment variable as an alternative to `setup`.

---

## MCP Server

Expose Qwen Council as tools for any MCP-compatible client (Claude Desktop, Cursor, etc.):

```bash
# Install MCP SDK
pip install mcp httpx

# Run in stdio mode (for Claude Desktop, Cursor)
QWEN_COUNCIL_API_URL=http://localhost:8000 python3 -m backend.mcp_server
```

### Available Tools

| Tool | Description |
|:-----|:------------|
| `review_code(code, instruction)` | Submit code for multi-agent council review |
| `chat(message, session_id)` | Ask the expert panel a question |
| `list_sessions(limit)` | List past review/chat sessions |
| `get_session(session_id)` | Get details of a specific session |

### Claude Desktop Config

```json
{
  "mcpServers": {
    "qwen-council": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/path/to/qwen-council",
      "env": { "QWEN_COUNCIL_API_URL": "http://localhost:8000" }
    }
  }
}
```

---

## API Documentation

Interactive Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`
OpenAPI spec: `http://localhost:8000/openapi.json`

---

## LLM Provider Abstraction

Qwen Council uses an abstraction layer (`backend/llm/provider.py`) so you can swap the underlying LLM provider without changing agent code:

```python
from backend.llm.provider import LLMProvider, LLMResponse, get_provider, set_provider

# Use default Qwen provider
provider = get_provider()
response = await provider.complete(
    model="qwen3-coder-plus",
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=256,
)

# Swap to a custom provider (for testing or different LLM)
class MyProvider(LLMProvider):
    async def complete(self, model, messages, **kwargs):
        return LLMResponse(content="Custom response", model=model)

set_provider(MyProvider())
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

---

## Deployment on Alibaba Cloud ECS

```bash
ssh root@your-ecs-ip
git clone https://github.com/02NIN20/qwen-council.git
cd qwen-council
cp .env.example .env
nano .env   # Set qwen_api_key
sudo bash deploy.sh
```

### Persistence after reboot

```bash
sudo systemctl enable docker
```

With `restart: unless-stopped` in docker-compose.yml, all containers auto-start after ECS reboot.

---

## Built for

[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society

---

## License

MIT
