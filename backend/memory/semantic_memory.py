"""Level 3: Semantic memory — pgvector embeddings for consolidated patterns.

Uses the Qwen Cloud API (text-embedding-v3) to generate 1536-dimension
embeddings stored in a PostgreSQL table with pgvector extension.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI
from pgvector.sqlalchemy import Vector
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.db import SemanticMemory

logger = logging.getLogger(__name__)

# Maximum number of semantic patterns to inject into agent prompts
MAX_INJECTION_COUNT = 5


class SemanticMemoryManager:
    """Manages semantic memory (pgvector) persistence and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            timeout=settings.qwen_timeout_seconds,
        )
        self._embedding_model = settings.qwen_embedding_model

    # ──────────────────────────────────────────────
    #  Write
    # ──────────────────────────────────────────────

    async def consolidate(
        self,
        pattern: str,
        category: str,
    ) -> SemanticMemory | None:
        """Store a new semantic pattern with its embedding.

        If a similar pattern already exists, increment its strength instead.
        """
        # Check for existing similar pattern
        existing = await self._find_similar(pattern, threshold=0.85)
        if existing is not None:
            existing.strength += 1
            await self.session.commit()
            logger.debug(
                "Incremented strength of existing pattern '%s' (now %d)",
                existing.pattern_text[:60],
                existing.strength,
            )
            return existing

        # Generate embedding
        embedding = await self._generate_embedding(pattern)
        if embedding is None:
            logger.warning("Failed to generate embedding for pattern, skipping")
            return None

        record = SemanticMemory(
            pattern_text=pattern,
            embedding=embedding,
            category=category,
            strength=1,
        )
        self.session.add(record)
        await self.session.commit()
        logger.debug(
            "Consolidated new semantic pattern: '%s' [%s]",
            pattern[:60],
            category,
        )
        return record

    # ──────────────────────────────────────────────
    #  Read
    # ──────────────────────────────────────────────

    async def retrieve_relevant(
        self,
        code_context: str,
        limit: int = MAX_INJECTION_COUNT,
    ) -> list[SemanticMemory]:
        """Retrieve semantic patterns relevant to the given code context.

        Uses vector cosine similarity via pgvector.
        Only returns patterns with strength >= 1 and above the injection threshold.
        """
        embedding = await self._generate_embedding(code_context)
        if embedding is None:
            return []

        threshold = settings.semantic_injection_threshold

        # Build the vector similarity query
        query = (
            select(
                SemanticMemory,
                SemanticMemory.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(SemanticMemory.strength >= 1)
            .order_by(text("distance ASC"))
            .limit(limit)
        )

        try:
            result = await self.session.execute(query)
            rows = result.all()
        except Exception:
            logger.exception("pgvector similarity query failed")
            return []

        patterns: list[SemanticMemory] = []
        for row in rows:
            # row is a tuple (SemanticMemory, distance)
            record = row[0]
            distance = row[1]
            similarity = 1.0 - distance
            if similarity >= (threshold - 0.2):  # Allow slightly lower threshold
                patterns.append(record)

        return patterns

    async def get_all(self) -> list[SemanticMemory]:
        """Return all semantic memory records ordered by strength descending."""
        result = await self.session.execute(
            select(SemanticMemory).order_by(SemanticMemory.strength.desc())
        )
        return list(result.scalars().all())

    async def get_by_category(self, category: str) -> list[SemanticMemory]:
        """Return records filtered by category."""
        result = await self.session.execute(
            select(SemanticMemory)
            .where(SemanticMemory.category == category)
            .order_by(SemanticMemory.strength.desc())
        )
        return list(result.scalars().all())

    # ──────────────────────────────────────────────
    #  Internal helpers
    # ──────────────────────────────────────────────

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """Generate an embedding vector using Qwen Cloud API."""
        try:
            response = await self._client.embeddings.create(
                model=self._embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception:
            logger.exception("Failed to generate embedding")
            return None

    async def _find_similar(
        self, pattern: str, threshold: float = 0.85
    ) -> SemanticMemory | None:
        """Find an existing pattern similar to *pattern* using cosine similarity."""
        embedding = await self._generate_embedding(pattern)
        if embedding is None:
            return None

        query = (
            select(SemanticMemory)
            .order_by(
                SemanticMemory.embedding.cosine_distance(embedding).asc()
            )
            .limit(1)
        )
        try:
            result = await self.session.execute(query)
            record = result.scalar_one_or_none()
            if record is None:
                return None
            # Calculate similarity
            sim_query = select(
                SemanticMemory.embedding.cosine_distance(embedding)
            ).where(SemanticMemory.id == record.id)
            sim_result = await self.session.execute(sim_query)
            distance = sim_result.scalar_one()
            similarity = 1.0 - distance
            if similarity >= threshold:
                return record
        except Exception:
            logger.exception("Similarity search failed")
        return None
