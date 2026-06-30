"""Level 2: Episodic memory — PostgreSQL-backed with forget curve.

Each session gets a score that decays over time and recovers on reference.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db import EpisodicMemory, code_hash

logger = logging.getLogger(__name__)


class EpisodicMemoryManager:
    """Manages episodic memory persistence and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ──────────────────────────────────────────────
    #  Write
    # ──────────────────────────────────────────────

    async def save(
        self,
        session_id: str,
        code: str,
        findings: list[dict] | list,
        score: float = 1.0,
    ) -> EpisodicMemory:
        """Save a new session to episodic memory.

        If *session_id* already exists, it is updated.
        """
        # Check for existing
        existing = await self._get_by_session_id(session_id)
        if existing is not None:
            existing.code = code
            existing.code_hash = code_hash(code)
            existing.findings_json = json.dumps(
                findings, ensure_ascii=False, default=str
            )
            existing.score = score
            existing.last_referenced_at = datetime.now(timezone.utc)
            await self.session.commit()
            logger.debug("Updated episodic memory for '%s'", session_id)
            return existing

        h = code_hash(code)
        findings_str = json.dumps(findings, ensure_ascii=False, default=str)
        record = EpisodicMemory(
            id=session_id,
            session_id=session_id,
            code_hash=h,
            code=code,
            findings_json=findings_str,
            score=score,
        )
        self.session.add(record)
        await self.session.commit()
        logger.debug("Saved episodic memory for '%s'", session_id)
        return record

    # ──────────────────────────────────────────────
    #  Read
    # ──────────────────────────────────────────────

    async def get(self, session_id: str) -> EpisodicMemory | None:
        """Retrieve a session and update its score (recovery on reference)."""
        record = await self._get_by_session_id(session_id)
        if record is not None:
            await self._apply_reference_bump(record)
        return record

    async def list_recent(
        self, limit: int = 20, min_score: float | None = None
    ) -> list[EpisodicMemory]:
        """List recent sessions ordered by creation time.

        Parameters
        ----------
        limit : int
            Max number of sessions to return.
        min_score : float | None
            If set, only return sessions with score >= this value.
        """
        query = select(EpisodicMemory).order_by(
            EpisodicMemory.created_at.desc()
        )
        if min_score is not None:
            query = query.where(EpisodicMemory.score >= min_score)
        query = query.limit(limit)
        result = await self.session.execute(query)
        records = list(result.scalars().all())
        # Apply decay to all loaded records
        for rec in records:
            rec.score = self._apply_decay(rec)
        await self.session.commit()
        return records

    async def get_relevant(
        self, code_context: str, limit: int = 5
    ) -> list[EpisodicMemory]:
        """Retrieve sessions relevant to *code_context* with score > threshold.

        Uses keyword overlap as a simple relevance heuristic.
        """
        threshold = settings.episodic_archive_threshold
        query = (
            select(EpisodicMemory)
            .where(EpisodicMemory.score > threshold)
            .order_by(EpisodicMemory.score.desc())
            .limit(limit * 3)  # Fetch extra to account for decay
        )
        result = await self.session.execute(query)
        records = list(result.scalars().all())

        # Apply decay and filter
        valid: list[EpisodicMemory] = []
        for rec in records:
            rec.score = self._apply_decay(rec)
            if rec.score > threshold:
                valid.append(rec)

        # Sort by keyword overlap
        context_keywords = set(
            w.lower() for w in code_context.split() if len(w) > 3
        )
        valid.sort(
            key=lambda r: (
                len(context_keywords & set(r.code.lower().split())),
                r.score,
            ),
            reverse=True,
        )

        return valid[:limit]

    # ──────────────────────────────────────────────
    #  Maintain
    # ──────────────────────────────────────────────

    async def apply_decay_all(self) -> int:
        """Apply decay to all records. Returns number of records archived."""
        result = await self.session.execute(
            select(EpisodicMemory)
        )
        records = list(result.scalars().all())
        archived = 0
        threshold = settings.episodic_archive_threshold

        for rec in records:
            new_score = self._apply_decay(rec)
            if new_score < threshold:
                # Archive: set score to 0 but keep record
                rec.score = 0.0
                archived += 1
                logger.debug(
                    "Archived episodic memory '%s' (score %.2f)",
                    rec.session_id,
                    new_score,
                )
            else:
                rec.score = new_score

        await self.session.commit()
        return archived

    async def cleanup_excess(self, max_active: int | None = None) -> int:
        """Remove excess active sessions beyond *max_active*.

        Returns number of deleted records.
        """
        if max_active is None:
            max_active = settings.episodic_max_active

        # Count active (score > threshold)
        threshold = settings.episodic_archive_threshold
        result = await self.session.execute(
            select(EpisodicMemory)
            .where(EpisodicMemory.score > threshold)
            .order_by(EpisodicMemory.score.asc())
        )
        active = list(result.scalars().all())
        if len(active) <= max_active:
            return 0

        excess = len(active) - max_active
        to_delete = active[:excess]
        for rec in to_delete:
            await self.session.execute(
                delete(EpisodicMemory).where(
                    EpisodicMemory.session_id == rec.session_id
                )
            )
        await self.session.commit()
        logger.info("Cleaned up %d excess episodic records", excess)
        return excess

    # ──────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────

    async def _get_by_session_id(
        self, session_id: str
    ) -> EpisodicMemory | None:
        result = await self.session.execute(
            select(EpisodicMemory).where(
                EpisodicMemory.session_id == session_id
            )
        )
        return result.scalar_one_or_none()

    async def _apply_reference_bump(self, record: EpisodicMemory) -> None:
        """Increase score when a session is referenced."""
        recovery = settings.episodic_recovery_on_reference
        now = datetime.now(timezone.utc)
        record.score = min(1.0, record.score + recovery)
        record.last_referenced_at = now
        await self.session.commit()
        logger.debug(
            "Score bump for '%s': %.2f", record.session_id, record.score
        )

    def _apply_decay(self, record: EpisodicMemory) -> float:
        """Calculate time-based decay for a record without saving."""
        if record.last_referenced_at is None:
            ref_time = record.created_at
        else:
            ref_time = record.last_referenced_at

        now = datetime.now(timezone.utc)

        # Ensure timezone awareness
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        days_since = (now - ref_time).total_seconds() / 86400.0
        decay = settings.episodic_decay_per_day * days_since
        new_score = max(0.0, record.score - decay)
        return new_score
