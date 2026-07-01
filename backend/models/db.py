"""SQLAlchemy async engine, session factory, and declarative base.

Also defines the ORM models for episodic and semantic memory tables.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, AsyncGenerator

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.config import settings

# ──────────────────────────────────────────────
#  Engine & session
# ──────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Return True if the database is reachable."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


# ──────────────────────────────────────────────
#  Declarative base
# ──────────────────────────────────────────────


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────
#  Helper: code hash
# ──────────────────────────────────────────────


def code_hash(code: str) -> str:
    """Return a SHA-256 hex digest of *code*."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────
#  Episodic memory table (Level 2)
# ──────────────────────────────────────────────


class EpisodicMemory(Base):
    __tablename__ = "episodic_memory"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    findings_json: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_referenced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def get_findings(self) -> list[dict[str, Any]]:
        """Deserialize stored findings JSON."""
        return json.loads(self.findings_json)

    def set_findings(self, findings: Any) -> None:
        """Serialize findings to JSON string."""
        if isinstance(findings, str):
            self.findings_json = findings
        else:
            self.findings_json = json.dumps(findings, ensure_ascii=False, default=str)


# ──────────────────────────────────────────────
#  Semantic memory table (Level 3 — pgvector)
# ──────────────────────────────────────────────


class SemanticMemory(Base):
    __tablename__ = "semantic_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(1536), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    strength: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ──────────────────────────────────────────────
#  Create all tables
# ──────────────────────────────────────────────


async def init_db() -> None:
    """Create all tables if they do not exist.

    Call once at application startup.
    The pgvector extension must already be enabled on the PostgreSQL instance:
        CREATE EXTENSION IF NOT EXISTS vector;
    """
    async with engine.begin() as conn:
        # Ensure pgvector extension is present
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
