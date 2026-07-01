# Building a Multi-Agent Society with Qwen Cloud — My Hackathon Journey

> **Track 3: Agent Society** — Global AI Hackathon Series with Qwen Cloud
> 
> *Published: July 2026*

---

When I first read the Track 3 description — *"Design a multi-agent collaboration system where multiple Agents with distinct capabilities work together through task division, dialogue, and negotiation"* — I knew I had to build something that went beyond the typical "ask an AI and get an answer" pattern.

What if agents could **debate** with each other? What if they could **disagree**, **negotiate**, and **reach consensus** — just like a real team of experts?

That's how **Qwen Council** was born.

## The Problem

Single-agent AI code review has a fundamental limitation: one model, one perspective. It might catch SQL injection but miss architectural debt. It might flag a performance issue but overlook accessibility problems.

In the real world, code reviews are done by **teams** — security engineers, architects, QA specialists, performance experts. Each brings a different lens. Why should AI be any different?

## The Architecture

Qwen Council is a multi-agent system with **14 specialised agents** running on Qwen Cloud, deployed on Alibaba Cloud ECS with PostgreSQL + pgvector for memory.

### Two Modes of Operation

**1. Code Review (Council Mode)** — 6 agents with distinct expertise:
- **Security**: OWASP Top 10, SQL injection, XSS, secrets
- **Architecture**: SOLID, coupling, scalability, design patterns
- **Quality**: Code style, dead code, complexity, tests
- **Performance**: N+1 queries, caching, inefficient loops
- **UX**: Accessibility, i18n, error messages
- **Vision**: Screenshot/diagram analysis (qwen-vl-plus)

**2. General Chat (Expert Panel)** — 8 personality-based agents:
- Scientist (Feynman), Technologist (Torvalds), Philosopher (Socrates), Historian (Harari), Artist (Miyazaki), Psychologist (Jung), Strategist (Sun Tzu), Generalist (Franklin)

### The Communication Protocol

The key innovation is an **inter-agent communication protocol** based on cognitive linguistics:

- **Inverted Pyramid**: Each finding starts with the conclusion first — one line that any agent can grasp in 1 second.
- **Given-New**: In debate rounds, agents explicitly reference each other's findings: *"Agreeing with Security on SQL injection at line 45, I found the same pattern at line 78."*
- **High Cohesion**: Direct references to code lines, CWE identifiers, and concrete evidence.

### 3-Level Memory Architecture

| Level | Storage | Purpose |
|-------|---------|---------|
| Working Memory | In-memory dict | Current session state |
| Episodic Memory | PostgreSQL | Past sessions with forgetting curve (-0.1/day decay) |
| Semantic Memory | PostgreSQL + pgvector | Consolidated patterns via vector embeddings |

## The Debate Cycle

Each code review goes through **4 rounds**:

1. **Individual Analysis** — Each agent reviews the code independently
2. **Cross-Debate** — Agents see each other's findings and apply Given-New referencing
3. **Refinement** — Agents update positions: KEEP, MODIFY, or WITHDRAW findings
4. **Negotiation** — When agents disagree on severity, a negotiation round forces consensus

The final report includes executive summary, risk heatmap, detailed findings with votes, consensus scores, and a remediation roadmap.

## The Results

I ran a benchmark comparing a single generalist agent vs the full council on the same code:

| Metric | Single-Agent | Multi-Agent | Change |
|--------|-------------|-------------|--------|
| Total findings | 12 | 127 | **+958%** |
| Categories covered | 6/6 | 6/6 | 100% overlap |
| Unique findings | 0 | 115 | +115 |

The multi-agent system found **10.6x more issues** while preserving 100% of what the single agent caught. That's the power of diverse perspectives.

## Building with Qwen Cloud

The entire system runs on **qwen3-coder-plus** for code analysis, **qwen-vl-plus** for visual inspection, and **text-embedding-v3** for semantic memory. The Qwen Cloud API's OpenAI-compatible interface made integration seamless — I could use the same `openai` Python library I already knew.

Key technical decisions:
- **FastAPI** for the async backend (Python 3.11)
- **React + Vite** for the real-time frontend with SSE streaming
- **PostgreSQL + pgvector** for hybrid relational + vector search
- **Docker Compose** for one-command deployment on Alibaba ECS

## What I Learned

1. **Agents need boundaries**. Initially, every agent answered every question with equal competence. Adding explicit domain restrictions made the system much more realistic — a technologist shouldn't opine on philosophy.

2. **Routing matters**. A keyword-based classifier routes questions to 1-3 relevant agents. Getting this right is crucial — misrouting wastes tokens and dilutes quality.

3. **Memory is hard**. The forgetting curve (score decays -0.1/day, recovers +0.3 on reference) required careful tuning. Too aggressive and sessions disappear; too lenient and the database fills up.

4. **SSE streaming transforms UX**. Watching agents respond in real-time — seeing the Security agent flag an issue, then Architecture agree, then Performance add a new finding — is dramatically more engaging than waiting for a single response.

## What's Next

- MCP integration for tool calling
- Human-in-the-loop checkpoints for critical decisions
- Multi-file cross-referencing for large codebases
- Export findings to GitHub Issues or Jira

## Repository

The full source code is open source under MIT license:

**[github.com/02NIN20/qwen-council](https://github.com/02NIN20/qwen-council)**

---

*Built for the [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society.*
