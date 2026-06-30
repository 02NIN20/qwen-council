"""FastAPI application entry point for Qwen Council.

Endpoints:
  POST /api/review       — Run the council on submitted code
  GET  /api/sessions      — List previous sessions
  GET  /api/sessions/{id} — Session detail
  GET  /api/memory/patterns — Consolidated semantic patterns
  GET  /api/health        — Health check
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MemoryPattern,
    ReviewRequest,
    ReviewResponse,
    SessionDetail,
    SessionSummary,
)

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


@app.post("/api/chat", response_model=ChatResponse)
async def chat_followup(payload: ChatRequest):
    """Answer a follow-up question about a previous review session."""
    from openai import AsyncOpenAI
    try:
        client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
        )

        system_prompt = (
            "You are a code review assistant answering follow-up questions about a previous analysis. "
            "Use the provided context (findings, code, discussion) to give specific, actionable answers. "
            "Be concise but thorough. If you need more context, say so."
        )

        user_content = f"### Context from code review:\n{payload.context or 'No additional context provided.'}\n\n### Question:\n{payload.message}"

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
        )
    except Exception:
        logger.exception("Chat follow-up failed")
        raise HTTPException(status_code=500, detail="Failed to generate response")


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
