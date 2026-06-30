# 📋 Qwen Council — Multi-Agent Code Review System

**Track 3: Agent Society** — Global AI Hackathon Series with Qwen Cloud

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## 🧠 What is Qwen Council?

Qwen Council is a **multi-agent system** where 5 specialised AI agents debate collaboratively to perform code review. Each agent has a unique expertise (Security, Architecture, Quality, Performance, UX) and follows a structured **Inverted Pyramid communication protocol** inspired by cognitive linguistics — making debates efficient, explicit, and self-sufficient.

### Key Innovations

| Innovation | Description |
|:-----------|:------------|
| **🗣️ Linguistic Protocol** | Inter-agent messages follow **Inverted Pyramid** (finding → detail → impact → proposal) with **Given-New** referencing for high cohesion |
| **🧠 3-Level Memory** | Working (volatile) → Episodic (PostgreSQL with forgetting curve) → Semantic (pgvector embeddings) |
| **⚖️ Consensus Engine** | Cross-agent voting with weighted consensus scoring |
| **🔄 Debate Cycle** | 3 rounds: Individual Analysis → Cross-Debate → Final Refinement |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    REACT FRONTEND                           │
│  CodeInput → AgentGrid → DebateTimeline → FinalReport      │
└──────────────────────────┬─────────────────────────────────┘
                           │ HTTP (REST)
┌──────────────────────────▼─────────────────────────────────┐
│                    FASTAPI BACKEND                           │
│  POST /api/review  │  GET /api/sessions  │  GET /api/health │
└──────────────────────────┬─────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│  AGENTS (5)  │  │   COUNCIL    │  │     MEMORY       │
│  ┌────────┐  │  │  ┌────────┐  │  │  ┌────────────┐  │
│  │🛡️  Sec│  │  │  │Round 1 │  │  │  │ Working    │  │
│  │🏗️  Arch│  │  │  │Round 2 │  │  │  │ Episodic   │  │
│  │📐  Qual│  │  │  │Round 3 │  │  │  │ Semantic   │  │
│  │⚡  Perf│  │  │  │Synth   │  │  │  │ (pgvector) │  │
│  │♿  UX  │  │  │  └────────┘  │  │  └────────────┘  │
│  └────────┘  │  └──────────────┘  └──────────────────┘
└──────┬───────┘
       │
       ▼
┌────────────────────────────────────────────────────────────┐
│                    QWEN CLOUD API                            │
│  https://dashscope-intl.aliyuncs.com/compatible-mode/v1     │
└────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker + docker-compose (optional)
- Qwen Cloud API key ([get one here](https://www.qwencloud.com/challenge/hackathon/voucher-application))

### 1. Clone & Setup

```bash
git clone https://github.com/YOUR_USERNAME/qwen-council.git
cd qwen-council

# Backend
pip install -r backend/requirements.txt
cp .env.example .env  # Add your QWEN_API_KEY

# Frontend
cd frontend
npm install
```

### 2. Run Locally

```bash
# Terminal 1: Backend
cd backend
uvicorn main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Open http://localhost:5173

### 3. Or Run with Docker

```bash
docker-compose up --build
```

---

## 🧪 API Endpoints

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/review` | Submit code for council review |
| `GET` | `/api/sessions` | List past review sessions |
| `GET` | `/api/sessions/{id}` | Get session details |
| `GET` | `/api/memory/patterns` | Get consolidated semantic patterns |
| `GET` | `/api/health` | Health check |

---

## 🧑‍⚖️ Council Agents

| Agent | Icon | Expertise | Prompt Focus |
|:------|:----:|:----------|:-------------|
| **Security** | 🛡️ | OWASP Top 10, SQL injection, XSS, secrets | Vulnerability detection |
| **Architecture** | 🏗️ | SOLID, coupling, scalability, patterns | System design quality |
| **Quality** | 📐 | Code style, dead code, complexity, tests | Code maintainability |
| **Performance** | ⚡ | N+1 queries, caching, inefficient loops | Runtime efficiency |
| **UX** | ♿ | Accessibility, i18n, error messages, contrast | User experience |

---

## 💾 Memory System

```
                  ┌──────────────────┐
                  │  WORKING MEMORY  │  Session-scoped, volatile
                  │   (Python dict)  │
                  └────────┬─────────┘
                           │ session ends
                  ┌────────▼─────────┐
                  │ EPISODIC MEMORY  │  PostgreSQL + forgetting curve
                  │   (score decay)  │  (-0.1/day, +0.3/reference)
                  └────────┬─────────┘
                           │ pattern 3+ times
                  ┌────────▼─────────┐
                  │ SEMANTIC MEMORY  │  pgvector embeddings
                  │   (permanent)    │  Injected when score > 0.5
                  └──────────────────┘
```

---

## 🗣️ Communication Protocol

Each agent message follows the **Inverted Pyramid** format:

```
FINDING: SQL injection vulnerability at user input handling
··· Detail: src/app.py line 45: cursor.execute(f"SELECT * FROM users WHERE id = {user_input}")
··· Impact: Critical
··· Proposal: Use parameterised queries: cursor.execute("SELECT * FROM users WHERE id = ?", (user_input,))
```

In rounds 2+, agents apply **Given-New** referencing:

```
FINDING: Agreeing with Security on the SQL injection, I also found the same pattern at line 78
··· Detail: src/app.py line 78: same f-string pattern in delete_user()
··· Impact: Critical — 2 attack vectors identified
··· Proposal: Create a safe_query() helper that always uses parameterisation
```

---

## 🎥 Demo Video

[YouTube video coming soon]

---

## 📄 License

MIT

---

## 🏆 Built for

[Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society
