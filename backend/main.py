"""FastAPI application entry point for Qwen Council.

Endpoints:
  POST /api/review       — Run the council on submitted code
  GET  /api/sessions      — List previous sessions
  GET  /api/sessions/{id} — Session detail
  GET  /api/memory/patterns — Consolidated semantic patterns
  GET  /api/health        — Health check
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from backend.config import settings
from backend.council.orchestrator import CouncilOrchestrator
from backend.memory.episodic_memory import EpisodicMemoryManager
from backend.memory.semantic_memory import SemanticMemoryManager
from backend.models.db import (
    EpisodicMemory,
    SemanticMemory,
    async_session_factory,
    check_db_connection,
    get_session,
    init_db,
)
from backend.models.schemas import (
    AgentContribution,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MemoryPattern,
    ReviewRequest,
    ReviewResponse,
    SessionDetail,
    SessionSummary,
)
from backend.agents.security_agent import SecurityAgent
from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.quality_agent import QualityAgent
from backend.agents.performance_agent import PerformanceAgent
from backend.agents.ux_agent import UXAgent
from backend.agents.vision_agent import VisionAgent

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ──────────────────────────────────────────────
#  Lifespan
# ──────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    logger.info("Starting Qwen Council API")
    # Log API key status (safely — never log the actual key)
    key_status = "SET" if settings.qwen_api_key else "NOT SET — agents will return NO_FINDINGS!"
    key_preview = (settings.qwen_api_key[:8] + "..." + settings.qwen_api_key[-4:]) if settings.qwen_api_key else "N/A"
    logger.info("Qwen API key: %s (len=%d, preview=%s)", key_status, len(settings.qwen_api_key), key_preview)
    logger.info("Qwen model: %s", settings.qwen_model)
    logger.info("Qwen base URL: %s", settings.qwen_base_url)
    logger.info("Database URL: %s", settings.database_url.replace(settings.database_url.split(":")[2].split("@")[0], "****") if "@" in settings.database_url else settings.database_url)
    try:
        await init_db()
        logger.info("Database tables initialised")
    except Exception:
        logger.warning(
            "Database initialisation failed — continuing without DB. "
            "Set DATABASE_URL if you need persistence."
        )
    yield
    logger.info("Shutting down Qwen Council API")


# ──────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────

app = FastAPI(
    title="Qwen Council API",
    description="Multi-agent code review system with memory",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

orchestrator = CouncilOrchestrator()


# ──────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────


@app.post("/api/review", response_model=ReviewResponse)
async def review_code(payload: ReviewRequest):
    """Execute the council on the provided source code.

    If *session_id* is provided, it resumes an existing session context.
    Otherwise a new session is created.
    """
    try:
        report, session_id, round_data = await orchestrator.run_council(
            code=payload.code or "",
            session_id=payload.session_id,
            image_url=payload.image_url,
            files=payload.files or None,
            instruction=payload.instruction,
        )

        return ReviewResponse(
            session_id=session_id,
            report=report,
            rounds_raw=round_data,
        )
    except Exception:
        logger.exception("Council execution failed")
        raise HTTPException(
            status_code=500, detail="Council execution failed"
        )


@app.post("/api/review/stream")
async def review_code_stream(payload: ReviewRequest):
    """Stream council progress via Server-Sent Events.

    Accepts the same ``ReviewRequest`` body as ``POST /api/review`` but
    returns a ``text/event-stream`` response with real-time progress events.
    """
    async def event_generator():
        """Inner async generator that formats council events as SSE lines."""
        try:
            async for event_type, data in orchestrator.stream_council(
                code=payload.code or "",
                session_id=payload.session_id,
                image_url=payload.image_url,
                files=payload.files or None,
                instruction=payload.instruction,
            ):
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        except Exception:
            logger.exception("Stream council failed")
            yield (
                "event: error\n"
                "data: "
                + json.dumps({
                    "message": "Council execution failed",
                    "detail": "Internal server error",
                })
                + "\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_general(payload: ChatRequest):
    """Multi-agent chat for ANY question.

    If session_id is provided with existing context, acts as follow-up
    using a single LLM call. Otherwise, routes the question to all 6
    specialised agents in parallel and synthesises a unified answer.
    """
    from openai import AsyncOpenAI

    try:
        # ── Follow-up mode (session + context) ──────────────────────
        if payload.session_id and payload.context:
            client = AsyncOpenAI(
                api_key=settings.qwen_api_key,
                base_url=settings.qwen_base_url,
            )
            system_prompt = (
                "You are a code review assistant answering follow-up questions about a previous analysis. "
                "Use the provided context (findings, code, discussion) to give specific, actionable answers. "
                "Be concise but thorough. If you need more context, say so."
            )
            user_content = (
                f"### Context from code review:\n{payload.context or 'No additional context provided.'}\n\n"
                f"### Question:\n{payload.message}"
            )
            resp = await client.chat.completions.create(
                model=settings.qwen_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=1000,
                temperature=0.3,
            )
            answer = resp.choices[0].message.content or "I couldn't generate a response."
            return ChatResponse(
                response=answer,
                session_id=payload.session_id,
                agent_contributions=[],
            )

        # ── General multi-agent mode ────────────────────────────────
        agents: dict[str, object] = {
            "security": SecurityAgent(),
            "architecture": ArchitectureAgent(),
            "quality": QualityAgent(),
            "performance": PerformanceAgent(),
            "ux": UXAgent(),
            "vision": VisionAgent(),
        }

        session_id = payload.session_id or f"chat-{uuid.uuid4().hex[:8]}"

        async def ask_agent(name: str, agent: object) -> dict:
            """Call a single agent's answer_question and return its contribution."""
            try:
                answer = await agent.answer_question(  # type: ignore[union-attr]
                    question=payload.message,
                    context=payload.context,
                )
                return {
                    "agent": name,
                    "role_description": getattr(agent, "role_description", ""),
                    "answer": answer,
                }
            except Exception as e:
                logger.error("Agent '%s' chat failed: %s", name, e)
                return {
                    "agent": name,
                    "role_description": getattr(agent, "role_description", ""),
                    "answer": f"[Agent {name} unavailable]",
                }

        tasks = [ask_agent(name, agent) for name, agent in agents.items()]
        contributions_data = await asyncio.gather(*tasks)

        # Synthesise final answer — a simple merge with attribution headers
        final_parts: list[str] = []
        for c in contributions_data:
            final_parts.append(
                f"### {c['agent'].title()} ({c['role_description']})\n{c['answer']}"
            )
        final = "Here are the perspectives from our expert panel:\n\n" + "\n\n".join(final_parts)

        return ChatResponse(
            response=final,
            session_id=session_id,
            agent_contributions=[
                AgentContribution(**c) for c in contributions_data
            ],
        )
    except Exception:
        logger.exception("Multi-agent chat failed")
        raise HTTPException(status_code=500, detail="Chat failed")


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest):
    """Stream multi-agent chat responses via Server-Sent Events.

    Emits one ``agent_responding`` event per agent when they start,
    an ``agent_response`` event when each agent finishes, and a final
    ``synthesis_complete`` event with the combined answer.
    """
    async def event_generator():
        try:
            agents: dict[str, object] = {
                "security": SecurityAgent(),
                "architecture": ArchitectureAgent(),
                "quality": QualityAgent(),
                "performance": PerformanceAgent(),
                "ux": UXAgent(),
                "vision": VisionAgent(),
            }

            session_id = payload.session_id or f"chat-{uuid.uuid4().hex[:8]}"

            # ── Follow-up shortcut ──────────────────────────────
            if payload.session_id and payload.context:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=settings.qwen_api_key,
                    base_url=settings.qwen_base_url,
                )
                yield "event: synthesis_complete\ndata: " + json.dumps({
                    "final_answer": "Follow-up mode — single response",
                    "session_id": session_id,
                    "contributions": [],
                }) + "\n\n"
                return

            # ── Fire all agents in parallel ─────────────────────
            async def run_agent(name: str, agent: object) -> tuple[str, str, str]:
                """Run a single agent and return (name, role, answer)."""
                role = getattr(agent, "role_description", "")
                try:
                    answer = await agent.answer_question(  # type: ignore[union-attr]
                        question=payload.message,
                        context=payload.context,
                    )
                except Exception as e:
                    logger.error("Agent '%s' stream chat failed: %s", name, e)
                    answer = f"[Agent {name} unavailable]"
                return name, role, answer

            tasks = [run_agent(name, agent) for name, agent in agents.items()]
            # Emit "agent_responding" before waiting
            for name, _ in agents.items():
                role = getattr(agents[name], "role_description", "")
                yield f"event: agent_responding\ndata: {json.dumps({'agent': name, 'role': role})}\n\n"

            # Wait for all in parallel
            results_data = await asyncio.gather(*tasks)

            # Emit individual responses
            for name, role, answer in results_data:
                yield f"event: agent_response\ndata: {json.dumps({'agent': name, 'answer': answer})}\n\n"

            # Build synthesis
            contributions = [
                {"agent": name, "role_description": role, "answer": answer}
                for name, role, answer in results_data
            ]
            final_parts: list[str] = []
            for c in contributions:
                final_parts.append(
                    f"### {c['agent'].title()} ({c['role_description']})\n{c['answer']}"
                )
            final = "Here are the perspectives from our expert panel:\n\n" + "\n\n".join(final_parts)

            yield "event: synthesis_complete\ndata: " + json.dumps({
                "final_answer": final,
                "session_id": session_id,
                "contributions": contributions,
            }) + "\n\n"

        except Exception:
            logger.exception("Stream chat failed")
            yield "event: error\ndata: " + json.dumps({
                "message": "Chat stream failed",
                "detail": "Internal server error",
            }) + "\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/sessions", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_session),
):
    """List recent sessions from episodic memory."""
    try:
        mgr = EpisodicMemoryManager(db)
        sessions = await mgr.list_recent(limit=limit)
        summaries: list[SessionSummary] = []
        for ses in sessions:
            try:
                findings = ses.get_findings()
                finding_count = len(findings) if isinstance(findings, list) else 0
            except Exception:
                finding_count = 0
            summaries.append(
                SessionSummary(
                    id=ses.session_id,
                    code_preview=ses.code[:120] if ses.code else "",
                    score=round(ses.score, 2),
                    created_at=ses.created_at.isoformat()
                    if ses.created_at
                    else "",
                    finding_count=finding_count,
                )
            )
        return summaries
    except Exception:
        logger.exception("Failed to list sessions")
        raise HTTPException(status_code=500, detail="Failed to list sessions")


@app.get("/api/sessions/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Get detailed information about a specific session."""
    try:
        mgr = EpisodicMemoryManager(db)
        record = await mgr.get(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionDetail(
            id=record.session_id,
            code=record.code,
            findings_json=record.get_findings(),
            score=round(record.score, 2),
            created_at=record.created_at.isoformat()
            if record.created_at
            else "",
            last_referenced_at=record.last_referenced_at.isoformat()
            if record.last_referenced_at
            else None,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get session detail")
        raise HTTPException(
            status_code=500, detail="Failed to get session detail"
        )


@app.get("/api/memory/patterns", response_model=list[MemoryPattern])
async def list_memory_patterns(
    category: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """List consolidated semantic memory patterns."""
    try:
        mgr = SemanticMemoryManager(db)
        if category:
            patterns = await mgr.get_by_category(category)
        else:
            patterns = await mgr.get_all()
        return [
            MemoryPattern(
                id=p.id,
                pattern_text=p.pattern_text,
                category=p.category,
                strength=p.strength,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in patterns
        ]
    except Exception:
        logger.exception("Failed to list memory patterns")
        raise HTTPException(
            status_code=500, detail="Failed to list memory patterns"
        )


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    db_ok = False
    try:
        db_ok = await check_db_connection()
    except Exception:
        pass
    return HealthResponse(status="ok", version="1.0.0", db_connected=db_ok)
