# Qwen Council — System Architecture

## Overview

Qwen Council is a multi-agent collaboration system deployed on Alibaba Cloud ECS, powered by Qwen Cloud APIs. It operates in two modes: **Code Review** (6 specialised agents with structured debate) and **General Chat** (8 personality-based agents with domain routing).

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER BROWSER                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  React Frontend (Vite + Tailwind CSS)                             │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │  │
│  │  │  Sidebar   │  │  ChatView    │  │  LiveCouncilStatus       │  │  │
│  │  │  Sessions  │  │  Messages    │  │  (SSE Stream Consumer)   │  │  │
│  │  │  [C] [R]   │  │  Input Bar   │  │  Real-time Agent Status  │  │  │
│  │  └────────────┘  └──────────────┘  └──────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                              HTTPS (port 80)
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                    ALIBABA CLOUD ECS INSTANCE                           │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  Nginx (Reverse Proxy)                                            │  │
│  │  /api/*     → http://backend:8000                                 │  │
│  │  /*         → /usr/share/nginx/html (static React build)          │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│              ┌─────────────────────┼─────────────────────┐              │
│              ▼                     ▼                     ▼              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │  FastAPI Backend │  │  PostgreSQL 15   │  │  Docker Network      │  │
│  │  (Uvicorn :8000) │  │  + pgvector      │  │  (bridge)            │  │
│  │                  │  │  :5432           │  │                      │  │
│  │  /api/review     │  │                  │  │  Containers:         │  │
│  │  /api/review/    │  │  Tables:         │  │  - nginx             │  │
│  │    stream        │  │  - episodic_     │  │  - backend           │  │
│  │  /api/chat       │  │    memory        │  │  - postgres          │  │
│  │  /api/chat/      │  │  - semantic_     │  │                      │  │
│  │    stream        │  │    memory        │  │  Volumes:            │  │
│  │  /api/sessions   │  │                  │  │  - pgdata            │  │
│  │  /api/health     │  │                  │  │  - frontend dist     │  │
│  └────────┬─────────┘  └──────────────────┘  └──────────────────────┘  │
│           │                                                             │
│           ▼                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    APPLICATION LAYER                               │  │
│  │                                                                   │  │
│  │  ┌─────────────────────┐    ┌──────────────────────────────────┐  │  │
│  │  │  CouncilOrchestrator │    │  Chat Router                     │  │  │
│  │  │  (Code Review Mode)  │    │  (General Chat Mode)             │  │  │
│  │  │                     │    │                                  │  │  │
│  │  │  Round 1: Individual│    │  _classify_question()            │  │  │
│  │  │  Round 2: Cross-    │    │  _route_question()               │  │  │
│  │  │    Debate           │    │  _synthesize_chat()              │  │  │
│  │  │  Round 3: Refine-   │    │                                  │  │  │
│  │  │    ment             │    │  Categories:                     │  │  │
│  │  │  Round 4: Negotia-  │    │  science, tech, history,         │  │  │
│  │  │    tion             │    │  philosophy, art, psychology,    │  │  │
│  │  │                     │    │  strategy, general               │  │  │
│  │  └─────────┬───────────┘    └──────────┬───────────────────────┘  │  │
│  │            │                           │                          │  │
│  │            ▼                           ▼                          │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │                    AGENT LAYER                               │  │  │
│  │  │                                                              │  │  │
│  │  │  Code Review Agents          │  Chat Agents                  │  │  │
│  │  │  ┌─────────────────────┐     │  ┌───────────────────────┐    │  │  │
│  │  │  │ SecurityAgent       │     │  │ ScientistAgent        │    │  │  │
│  │  │  │ ArchitectureAgent   │     │  │ TechnologistAgent     │    │  │  │
│  │  │  │ QualityAgent        │     │  │ PhilosopherAgent      │    │  │  │
│  │  │  │ PerformanceAgent    │     │  │ HistorianAgent        │    │  │  │
│  │  │  │ UXAgent             │     │  │ ArtistAgent           │    │  │  │
│  │  │  │ VisionAgent         │     │  │ PsychologistAgent     │    │  │  │
│  │  │  └─────────────────────┘     │  │ StrategistAgent       │    │  │  │
│  │  │                              │  │ GeneralistAgent       │    │  │  │
│  │  │  Domain: code review         │  └───────────────────────┘    │  │  │
│  │  │  Protocol: Inverted Pyramid  │  Domain: bounded per agent    │  │  │
│  │  │           + Given-New        │  Protocol: Q&A synthesis      │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │                    MEMORY LAYER                               │  │  │
│  │  │                                                              │  │  │
│  │  │  Level 1: Working Memory  →  Python dict (volatile)          │  │  │
│  │  │  Level 2: Episodic Memory →  PostgreSQL (forgetting curve)   │  │  │
│  │  │  Level 3: Semantic Memory →  pgvector (embeddings)           │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │                    LLM SYNTHESIZER                            │  │  │
│  │  │  qwen3-coder-plus → Executive Summary + Risk Heatmap +      │  │  │
│  │  │                      Remediation Roadmap + Agent Metrics     │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                         HTTPS (dashscope-intl API)
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                         QWEN CLOUD API                                   │
│  https://dashscope-intl.aliyuncs.com/compatible-mode/v1                  │
│                                                                          │
│  Models used:                                                            │
│  ┌──────────────────────┬────────────────────────────────────────────┐  │
│  │ qwen3-coder-plus     │ Code analysis, agent responses, synthesis  │  │
│  │ qwen-vl-plus         │ Visual inspection (screenshots, diagrams)  │  │
│  │ text-embedding-v3    │ Semantic memory embeddings (1536-dim)      │  │
│  └──────────────────────┴────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Code Review Flow

```
User submits code
       │
       ▼
POST /api/review (or /api/review/stream)
       │
       ▼
CouncilOrchestrator.start()
       │
       ├── Round 1: Each agent analyzes code independently
       │     └── Output: Inverted Pyramid findings
       │
       ├── Round 2: Cross-Debate
       │     └── Each agent sees others' findings, applies Given-New
       │
       ├── Round 3: Refinement
       │     └── Agents KEEP / MODIFY / WITHDRAW findings
       │
       ├── Round 4: Negotiation
       │     └── Detect severity disagreements, force consensus
       │
       ▼
LLM Synthesizer generates final report
       │
       ├── Executive Summary
       ├── Risk Overview (severity heatmap)
       ├── Detailed Review (per-finding with votes)
       ├── Remediation Roadmap
       └── Agent Metrics
       │
       ▼
Save to Episodic Memory (PostgreSQL)
       │
       ▼
Return JSON response to frontend
```

### General Chat Flow

```
User types question
       │
       ▼
POST /api/chat (or /api/chat/stream)
       │
       ▼
_classify_question() → category (science/tech/history/etc.)
       │
       ▼
_route_question() → 1-3 relevant agents
       │
       ▼
If session_id exists → load conversation history from DB
       │
       ▼
Each agent answers (domain-bounded, declines out-of-scope)
       │
       ▼
_synthesize_chat() → LLM merges responses into flowing answer
       │
       ▼
Append Q&A to existing findings in Episodic Memory
       │
       ▼
Return JSON response to frontend
```

---

## Memory Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY HIERARCHY                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Level 1: WORKING MEMORY (volatile)                 │   │
│  │  Storage: Python dict in orchestrator               │   │
│  │  Content: Current code, round findings, debate state│   │
│  │  Lifecycle: Session start → Session end             │   │
│  │  On close: Promoted to Episodic (Level 2)           │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Level 2: EPISODIC MEMORY (PostgreSQL)              │   │
│  │  Table: episodic_memory                             │   │
│  │  Content: Complete sessions (code, findings, votes) │   │
│  │  Retention: Last 20 active sessions                 │   │
│  │  Forgetting curve:                                  │   │
│  │    - Base score = 1.0                               │   │
│  │    - Decays -0.1/day without reference              │   │
│  │    - Recovers +0.3 when referenced                  │   │
│  │    - Archive threshold: score < 0.3                 │   │
│  │  Promotion: 3+ occurrences → Semantic (Level 3)     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Level 3: SEMANTIC MEMORY (PostgreSQL + pgvector)   │   │
│  │  Table: semantic_memory                             │   │
│  │  Content: User preferences, learned rules, patterns │   │
│  │  Embeddings: text-embedding-v3 (1536-dim)           │   │
│  │  Lifecycle: Permanent until explicit invalidation   │   │
│  │  Injection: Only score > 0.5 into new session prompts│   │
│  │  Retrieval: Cosine similarity via pgvector          │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALIBABA CLOUD ECS                             │
│  Region: ap-southeast-1 (Singapore)                             │
│  Instance: ecs.t6-c1m2.large (2 vCPU, 4 GB RAM)                │
│  OS: Ubuntu 22.04 LTS                                           │
│  Public IP: 47.84.227.185                                       │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Docker Compose (docker-compose.yml)                      │  │
│  │                                                           │  │
│  │  Services:                                                │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │   nginx     │  │   backend    │  │   postgres      │  │  │
│  │  │   :80       │  │   :8000      │  │   :5432         │  │  │
│  │  │             │  │   (Uvicorn)  │  │   (pgvector)    │  │  │
│  │  │  Reverse    │  │   FastAPI    │  │   PostgreSQL 15 │  │  │
│  │  │  Proxy      │  │   + Qwen     │  │   + Episodic    │  │  │
│  │  │             │  │   Cloud API  │  │   + Semantic    │  │  │
│  │  └─────────────┘  └──────────────┘  └─────────────────┘  │  │
│  │                                                           │  │
│  │  Volumes:                                                 │  │
│  │  - pgdata:/var/lib/postgresql/data                        │  │
│  │  - ./frontend/dist:/usr/share/nginx/html                  │  │
│  │                                                           │  │
│  │  Networks:                                                │  │
│  │  - qwen-council-net (bridge)                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| LLM API | Qwen Cloud (dashscope-intl) | qwen3-coder-plus, qwen-vl-plus, text-embedding-v3 |
| Backend | Python + FastAPI + Uvicorn | Python 3.11, FastAPI 0.115 |
| Frontend | React + TypeScript + Vite + Tailwind CSS | React 18, Vite 6 |
| Database | PostgreSQL + pgvector | PostgreSQL 15, pgvector 0.7 |
| Container | Docker + Docker Compose | Docker 27, Compose v2 |
| Cloud | Alibaba Cloud ECS | Ubuntu 22.04, 2 vCPU, 4 GB RAM |
| Reverse Proxy | Nginx | 1.24 |
| CI/CD | GitHub Actions → GitHub Container Registry | deploy.yml |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/review` | Submit code for council review |
| `POST` | `/api/review/stream` | Stream review progress via SSE |
| `POST` | `/api/chat` | General multi-agent chat |
| `POST` | `/api/chat/stream` | Stream chat responses via SSE |
| `GET` | `/api/sessions` | List past sessions |
| `GET` | `/api/sessions/{id}` | Get session details |
| `DELETE` | `/api/sessions/{id}` | Delete a session |
| `GET` | `/api/memory/patterns` | Get semantic memory patterns |
| `GET` | `/api/health` | Health check |

---

## Communication Protocol

### Inverted Pyramid Format

Each agent produces findings in this structure:

```
FINDING: SQL injection vulnerability at user input handling
... Detail: src/app.py line 45: cursor.execute(f"SELECT * FROM users WHERE id = {user_input}") (CWE-89)
... Impact: Critical
... Proposal: Use parameterised queries. BEFORE: cursor.execute(f"SELECT...{user_input}") AFTER: cursor.execute("SELECT...WHERE id = ?", (user_input,))
```

### Given-New Cross-Referencing (Rounds 2+)

```
FINDING: Agreeing with Security on SQL injection at line 45, I found the same pattern at line 78
... Detail: src/app.py line 78: same f-string pattern in delete_user() (CWE-89)
... Impact: Critical
... Proposal: Create a safe_query() helper that always uses parameterisation
```

---

## Source Code

Full repository: [github.com/02NIN20/qwen-council](https://github.com/02NIN20/qwen-council)
