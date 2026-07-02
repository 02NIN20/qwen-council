# Multi-Agent Council — Implementation Plan

## Project Information

- **Hackathon**: Global AI Hackathon Series with Qwen Cloud (Devpost)
- **Track**: 3 — Agent Society
- **Deadline**: July 9, 2026
- **Participants**: ~6,000
- **Prize**: $7,000 + $3,000 in cloud credits

## Concept

**Multi-Agent Council** is a multi-agent system where 6 role-based core agents with 15 sub-agents and 4 tools collaboratively debate to perform code review and advanced analysis. The key innovation is an **inter-agent communication protocol** based on cognitive linguistics principles (Inverted Pyramid, Given-New, high cohesion, self-sufficiency), where each message between agents is structured to minimise ambiguity and maximise debate efficiency.

---

## 1. Council Agents

| ID | Agent | Speciality |
|:---|:------|:-----------|
| `security` | 🛡️ Security | SQL injection, XSS, hardcoded secrets, authentication flaws, OWASP Top 10 |
| `architecture` | 🏗️ Architecture | Design patterns, coupling, SOLID principles, scalability, separation of concerns |
| `quality` | 📐 Quality | Code style, conventions, dead code, missing tests, cyclomatic complexity |
| `performance` | ⚡ Performance | N+1 queries, cache, inefficient loops, bottlenecks, blocking async code |
| `ux` | ♿ UX / Accessibility | Accessibility (a11y), i18n, error messages, contrast, keyboard navigation |

---

## 2. Communication Protocol

### Message Format: Inverted Pyramid

Each agent produces messages with this structure:

```
FINDING: [one-line main conclusion]
··· Detail: [concrete evidence: file, line, code fragment]
··· Impact: [Critical | High | Medium | Low]
··· Proposal: [suggested corrective action]
```

### Principles Applied

| Principle | Application in Protocol |
|:----------|:------------------------|
| **Inverted Pyramid** | The main finding comes FIRST (one line). The reader (another agent) grasps the essence in 1 second. |
| **Given-New** | In rounds 2+, each agent starts by explicitly referencing other agents' findings: *"Agreeing with [Agent] on [finding], I add that..."* |
| **High cohesion** | Explicit connectors (Agree, Disagree, Build upon). Direct references to code lines. |
| **Self-sufficiency** | Each message includes minimum context to be understood without reading previous messages. |
| **Minimalism** | No filler. Only: finding, evidence, impact, proposal. |

---

## 3. Debate Cycle

### Round 1: Individual Analysis
- Each agent receives the full source code
- Produces individual analysis in Inverted Pyramid format
- All 5 outputs collected for round 2

### Round 2: Cross-Debate
- Each agent receives the outputs from the other 4 agents
- Applies Given-New: "Agreeing/disagreeing with [Agent] on [finding]..."
- Can: confirm, refute, qualify, or add additional evidence
- All 5 updated outputs collected for round 3

### Round 3: Refinement
- Each agent sees the debates from round 2
- Updates position: KEEP, MODIFY, or WITHDRAW findings
- Produces final version of findings

### Final Synthesis
- A consolidator step produces the final report
- For each finding: each agent's vote, consensus level, priority
- Report format:

```
═══════════════════════════════════════════════════════
  CODE REVIEW REPORT — QWEN COUNCIL
═══════════════════════════════════════════════════════

FILE: src/app.py

FINDINGS:

1. [CRITICAL] SQL injection at line 45
   Votes: Security(CRITICAL) + Architecture(HIGH) + Quality(HIGH)
   Consensus: 5/5
   Proposal: Use parameterised queries

2. [HIGH] 300-line function without decomposition
   Votes: Quality(HIGH) + Architecture(HIGH) + Performance(MEDIUM)
   Consensus: 4/5 (UX abstains)
   Proposal: Extract validation and processing to separate modules
```

---

## 4. Memory Architecture (3 Levels + Forgetting Curve)

### Level 1: Working Memory (volatile)
| Attribute | Value |
|:----------|:------|
| Storage | Python dict in the orchestrator |
| Content | Current code being reviewed, current round findings, debate state |
| Lifecycle | Created at session start, destroyed at session end |
| On close | Findings promoted to Episodic (Level 2) |

### Level 2: Episodic Memory (PostgreSQL)
| Attribute | Value |
|:----------|:------|
| Storage | `episodic_memory` table in Alibaba RDS PostgreSQL |
| Content | Complete sessions: reviewed code, findings, votes, decisions, timestamp |
| Retention | Last 20 active sessions |
| Forgetting curve | Base score = 1.0. Decays -0.1/day without reference. Recovers +0.3 when referenced. Archive threshold: score < 0.3. |
| Promotion | If a pattern appears 3+ times across different sessions → promoted to Semantic |

### Level 3: Semantic Memory (PostgreSQL + pgvector)
| Attribute | Value |
|:----------|:------|
| Storage | `semantic_memory` table with pgvector embeddings |
| Content | User preferences, learned rules, consolidated patterns, architectural decisions |
| Embeddings | Generated with Qwen API (text-embedding) |
| Lifecycle | Permanent until explicit user invalidation |
| Injection | Only memories with score > 0.5 injected into new session prompts |

---

## 5. Tech Stack

| Component | Technology | Reason |
|:----------|:-----------|:-------|
| LLM | Qwen2.5 (Qwen Cloud API) | Required for the hackathon |
| Backend | Python 3.11 + FastAPI | Fast, async, typed |
| Database | PostgreSQL 15 + pgvector | Embeddings + hybrid queries |
| Frontend | React 18 + Tailwind CSS + Vite | Live debate dashboard, full UI control |
| Containers | Docker + docker-compose | Reproducible deployment |
| Cloud | Alibaba ECS + RDS | Hackathon requirement |
| API Base | https://dashscope-intl.aliyuncs.com/compatible-mode/v1 | OpenAI-compatible |
| CI/CD | GitHub Actions → ghcr.io → Alibaba ECS | Automated deployment from GitHub |

---

## 6. Repository Structure

```
multiagent-council/
├── README.md
├── LICENSE
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── plan.md
├── .github/
│   └── workflows/
│       └── deploy.yml
├── docs/
│   ├── architecture.md          # Diagram + description
│   └── alibaba-deployment.md    # Alibaba deployment proof
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Settings (Qwen API key, DB URL, etc.)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py           # Pydantic models
│   │   └── db.py                # SQLAlchemy engine + session
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py        # Base class for all agents
│   │   ├── security_agent.py
│   │   ├── architecture_agent.py
│   │   ├── quality_agent.py
│   │   ├── performance_agent.py
│   │   └── ux_agent.py
│   ├── council/
│   │   ├── __init__.py
│   │   ├── orchestrator.py      # 3-round debate orchestrator
│   │   ├── protocol.py          # Inverted Pyramid formatting
│   │   └── synthesizer.py       # Final synthesis + report
│   └── memory/
│       ├── __init__.py
│       ├── working_memory.py    # Level 1 (volatile)
│       ├── episodic_memory.py   # Level 2 (PostgreSQL + forgetting)
│       ├── semantic_memory.py   # Level 3 (pgvector)
│       └── consolidator.py      # Episodic → Semantic promotion
├── frontend/
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── package.json
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   └── council.ts
│   │   ├── components/
│   │   │   ├── CodeInput.tsx
│   │   │   ├── AgentCard.tsx
│   │   │   ├── AgentGrid.tsx
│   │   │   ├── DebateTimeline.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── FinalReport.tsx
│   │   │   └── CouncilHeader.tsx
│   │   └── types/
│   │       └── index.ts
│   └── public/
└── tests/
    ├── test_agents.py
    ├── test_council.py
    └── test_memory.py
```

---

## 7. Implementation Plan (7 Days)

| Day | Activity | Subagent |
|:---:|:---------|:---------|
| 1 | Backend: FastAPI + config + DB models + Docker | ✅ @backend-dev |
| 2 | Agents: 5 prompts + base_agent + protocol | ✅ @backend-dev |
| 3 | Council: orchestrator 3 rounds + synthesizer | ✅ @backend-dev |
| 4 | Memory: 3 levels + pgvector + forgetting curve + consolidation | ✅ @backend-dev |
| 5 | Frontend: React + Tailwind + Vite (CodeInput, AgentGrid, DebateTimeline, FinalReport) | ✅ @frontend-dev |
| 6 | Tests + Security + GitHub Actions CI/CD + Deploy to Alibaba ECS | @tester + @security + @devops |
| 7 | Video 3 min + Architecture diagram + README + Final docs | @documenter |

---

## 8. Video Structure (3 Minutes)

```
0:00-0:30 │ PROBLEM: Code reviews are slow and single-agent AI is limited
0:30-1:00 │ ARCHITECTURE: 5 specialists + Inverted Pyramid protocol + 3-level memory
1:00-2:00 │ DEMO: Paste code → Round 1 (individual) → Round 2 (debate) → Round 3 + Synthesis
2:00-2:30 │ MEMORY: "Remember my preference from last week?" → retrieves it
2:30-3:00 │ METRIC: Without council vs with council. Closing + repo link
```

---

## 9. Judging Criteria (How We Score)

| Criterion | Weight | How We Meet It |
|:----------|:------:|:---------------|
| **Technical Depth** | 30% | Qwen Cloud API + pgvector + multi-agent system with custom protocol |
| **Innovation & Creativity** | 30% | Linguistic inter-agent protocol (Inverted Pyramid + Given-New). Memory with forgetting curve. Unique. |
| **Problem Value & Impact** | 25% | Code review is a real, measurable problem. Saves hours/team/week. |
| **Presentation & Docs** | 15% | Clear diagram, concise video, polished README, live functional demo. |

---

## 10. MVP Definition

- [x] 5 agents respond with Inverted Pyramid format
- [x] 3 debate rounds work end-to-end
- [x] Synthesis report with votes and consensus
- [x] Episodic memory persists between sessions
- [x] Forgetting curve works (score decays and recovers)
- [x] React frontend shows live debate
- [ ] Deployed on Alibaba ECS with RDS
- [ ] GitHub Actions CI/CD pipeline
- [ ] 3-min video on YouTube
- [ ] Architecture diagram in docs/
- [ ] **Plus**: comparison "with council vs without council" with metrics
