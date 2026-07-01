---
title: "Building a Multi-Agent Society with Qwen Cloud — My Hackathon Journey"
published: true
tags: ai, machinelearning, hackathon, python, react
series: Global AI Hackathon Series with Qwen Cloud
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/default_background.png
description: How I built Qwen Council — a multi-agent system with 14 specialised AI agents that debate, negotiate, and reach consensus. Built with Qwen Cloud and deployed on Alibaba Cloud ECS.
---

When I first read the Track 3 description — *"Design a multi-agent collaboration system where multiple Agents with distinct capabilities work together through task division, dialogue, and negotiation"* — I knew I had to build something beyond the typical "ask an AI and get an answer" pattern.

What if agents could **debate** with each other? What if they could **disagree**, **negotiate**, and **reach consensus** — just like a real team of experts?

That's how **Qwen Council** was born.

## The Problem

Single-agent AI code review has a fundamental limitation: one model, one perspective. It might catch SQL injection but miss architectural debt. It might flag a performance issue but overlook accessibility problems.

In the real world, code reviews are done by **teams** — security engineers, architects, QA specialists. Each brings a different lens. Why should AI be any different?

## The Architecture

Qwen Council is a multi-agent system with **14 specialised agents** running on Qwen Cloud, deployed on Alibaba Cloud ECS.

### Two Modes

**Code Review** — 6 agents with distinct expertise (Security, Architecture, Quality, Performance, UX, Vision) review code through 4 structured debate rounds: individual analysis, cross-debate, refinement, and negotiation.

**General Chat** — 8 personality-based agents (inspired by Feynman, Torvalds, Socrates, Harari, Miyazaki, Jung, Sun Tzu, and Franklin) answer any question. Each agent has a strict domain boundary — they decline out-of-scope questions. A router classifies the question and activates only the 1-3 most relevant agents.

### The Communication Protocol

The key innovation is an inter-agent protocol based on cognitive linguistics:

- **Inverted Pyramid**: Each finding starts with the conclusion first — one line any agent can grasp in 1 second.
- **Given-New**: In debate rounds, agents explicitly reference each other's findings before adding new evidence.

### 3-Level Memory

Working memory (volatile) holds the current session. Episodic memory (PostgreSQL) stores past sessions with a forgetting curve that decays unused data. Semantic memory (PostgreSQL + pgvector) consolidates recurring patterns as vector embeddings.

## The Results

I ran a benchmark comparing a single generalist agent vs the full council on the same code:

| Metric | Single-Agent | Multi-Agent | Change |
|--------|-------------|-------------|--------|
| Total findings | 12 | 127 | **+958%** |
| Categories covered | 6/6 | 6/6 | 100% overlap |
| Unique findings | 0 | 115 | +115 |

The multi-agent system found **10.6x more issues** while preserving everything the single agent caught.

## Deploying on Alibaba Cloud

The entire stack runs on a single **Alibaba Cloud ECS instance** (2 vCPU, 4 GB RAM) in the Singapore region. Three Docker containers handle everything:

- **Nginx** serves the React frontend and routes API calls to the backend
- **FastAPI** orchestrates the agents and manages the memory system
- **PostgreSQL with pgvector** stores both session data and semantic embeddings

The backend connects to **Qwen Cloud** via its OpenAI-compatible API, using three models: **qwen3-coder-plus** for code analysis, **qwen-vl-plus** for visual inspection, and **text-embedding-v3** for semantic memory embeddings.

Why Alibaba Cloud? The ECS + Docker Compose setup gave me a simple, production-ready deployment with zero orchestration overhead. Qwen Cloud's native integration meant low-latency API calls from the ECS instance. And pgvector let me run hybrid relational + vector search in a single database — no separate vector DB needed.

## What I Learned

1. **Agents need boundaries**. Initially, every agent answered every question with equal competence. Adding explicit domain restrictions made the system much more realistic.

2. **Routing matters**. A keyword-based classifier routes questions to 1-3 relevant agents. Getting this right is crucial — misrouting wastes tokens and dilutes quality.

3. **Memory is hard**. The forgetting curve required careful tuning. Too aggressive and sessions disappear; too lenient and the database fills up.

4. **SSE streaming transforms UX**. Watching agents respond in real-time is dramatically more engaging than waiting for a single response.

## Repository

The full source code is open source under MIT license:

**[github.com/02NIN20/qwen-council](https://github.com/02NIN20/qwen-council)**

---

*Built for the [Global AI Hackathon Series with Qwen Cloud](https://qwencloud-hackathon.devpost.com/) — Track 3: Agent Society.*
