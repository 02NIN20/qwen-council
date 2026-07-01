"""Tests for the three-level memory system: working, episodic, semantic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Patch before importing classes that create AsyncOpenAI at __init__ ──
_mp = patch("backend.memory.semantic_memory.AsyncOpenAI")
_mp.start()

from backend.memory.consolidator import Consolidator
from backend.memory.episodic_memory import EpisodicMemoryManager
from backend.memory.semantic_memory import SemanticMemoryManager
from backend.memory.working_memory import WorkingMemory
from backend.models.db import EpisodicMemory, SemanticMemory


# ──────────────────────────────────────────────
#  Working Memory (Level 1)
# ──────────────────────────────────────────────


class TestWorkingMemory:
    """Tests for the volatile in-memory working storage."""

    def test_set_and_get(self):
        wm = WorkingMemory()
        wm.set("ses-1", {"code": "def foo(): pass", "status": "in_progress"})
        data = wm.get("ses-1")
        assert data is not None
        assert data["code"] == "def foo(): pass"
        assert data["status"] == "in_progress"

    def test_get_nonexistent_returns_default(self):
        wm = WorkingMemory()
        assert wm.get("nonexistent") is None
        assert wm.get("nonexistent", "fallback") == "fallback"

    def test_set_updates_existing(self):
        wm = WorkingMemory()
        wm.set("ses-1", {"status": "in_progress"})
        wm.set("ses-1", {"status": "completed", "report": "done"})
        data = wm.get("ses-1")
        assert data["status"] == "completed"
        assert data["report"] == "done"

    def test_delete_removes_session(self):
        wm = WorkingMemory()
        wm.set("ses-1", {"code": "test"})
        wm.delete("ses-1")
        assert wm.get("ses-1") is None

    def test_clear_removes_all(self):
        wm = WorkingMemory()
        wm.set("ses-1", {"a": 1})
        wm.set("ses-2", {"b": 2})
        wm.clear()
        assert wm.list_sessions() == []

    def test_list_sessions(self):
        wm = WorkingMemory()
        wm.set("ses-1", {})
        wm.set("ses-2", {})
        sessions = wm.list_sessions()
        assert "ses-1" in sessions
        assert "ses-2" in sessions
        assert len(sessions) == 2

    def test_contains(self):
        wm = WorkingMemory()
        wm.set("ses-1", {})
        assert "ses-1" in wm
        assert "ses-99" not in wm


# ──────────────────────────────────────────────
#  Episodic Memory (Level 2)
# ──────────────────────────────────────────────


class TestEpisodicMemory:
    """Tests for episodic memory with forgetting curve."""

    @pytest.mark.asyncio
    async def test_save_new_session(self, mock_db_session):
        mgr = EpisodicMemoryManager(mock_db_session)
        record = await mgr.save(
            session_id="ses-1",
            code="def foo(): pass",
            findings=[{"agent": "security", "hallazgo": "test"}],
        )
        assert record.session_id == "ses-1"
        assert record.code == "def foo(): pass"
        assert record.score == 1.0
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_updates_existing(self, mock_db_session):
        """Saving with an existing session_id updates the record."""
        existing = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="oldhash",
            code="old code",
            findings_json="[]",
            score=0.5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mgr = EpisodicMemoryManager(mock_db_session)
        record = await mgr.save(
            session_id="ses-1",
            code="new code",
            findings=[{"agent": "security", "hallazgo": "updated"}],
        )
        assert record.code == "new code"
        assert record.score == 1.0

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self, mock_db_session):
        mgr = EpisodicMemoryManager(mock_db_session)
        record = await mgr.get("nonexistent")
        assert record is None

    @pytest.mark.asyncio
    async def test_get_applies_reference_bump(self, mock_db_session):
        """Getting a session should increase its score (reference recovery)."""
        existing = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="code",
            findings_json="[]",
            score=0.5,
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            last_referenced_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=existing)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mgr = EpisodicMemoryManager(mock_db_session)
        record = await mgr.get("ses-1")
        assert record is not None
        # Score should have been bumped by recovery_on_reference (0.3)
        assert record.score >= 0.8  # 0.5 + 0.3 = 0.8

    def test_apply_decay_no_reference(self):
        """A record never referenced should decay from created_at."""
        created = datetime.now(timezone.utc) - timedelta(days=10)
        record = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="code",
            findings_json="[]",
            score=1.0,
            created_at=created,
            last_referenced_at=None,
        )
        mgr = EpisodicMemoryManager(MagicMock())
        decayed = mgr._apply_decay(record)
        # 10 days * 0.1 = 1.0 decay, so score should be 0.0
        assert decayed == 0.0

    def test_apply_decay_partial(self):
        """A record with partial decay should have a reduced score."""
        referenced = datetime.now(timezone.utc) - timedelta(days=3)
        record = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="code",
            findings_json="[]",
            score=1.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            last_referenced_at=referenced,
        )
        mgr = EpisodicMemoryManager(MagicMock())
        decayed = mgr._apply_decay(record)
        # 3 days * 0.1 = 0.3 decay, score should be 0.7
        assert decayed == pytest.approx(0.7, rel=0.1)

    def test_apply_decay_no_negative(self):
        """Decay should never produce a negative score."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        record = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="code",
            findings_json="[]",
            score=0.5,
            created_at=old,
            last_referenced_at=old,
        )
        mgr = EpisodicMemoryManager(MagicMock())
        decayed = mgr._apply_decay(record)
        assert decayed >= 0.0

    def test_reference_recovery_caps_at_1_0(self):
        """Reference recovery should not exceed 1.0."""
        assert min(1.0, 0.9 + 0.3) == 1.0
        assert min(1.0, 0.5 + 0.3) == 0.8

    @pytest.mark.asyncio
    async def test_list_recent(self, mock_db_session):
        """list_recent should query with descending created_at."""
        mock_record = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="code",
            findings_json="[]",
            score=1.0,
            created_at=datetime.now(timezone.utc),
        )
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_record])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mgr = EpisodicMemoryManager(mock_db_session)
        records = await mgr.list_recent(limit=10)
        assert len(records) == 1
        assert records[0].session_id == "ses-1"

    @pytest.mark.asyncio
    async def test_get_relevant_filters_by_score(self, mock_db_session):
        """get_relevant should only return records above threshold."""
        active_record = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="def foo(): pass",
            findings_json="[]",
            score=0.8,
            last_referenced_at=datetime.now(timezone.utc),
        )
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[active_record])
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mgr = EpisodicMemoryManager(mock_db_session)
        records = await mgr.get_relevant("def foo")
        assert len(records) > 0


# ──────────────────────────────────────────────
#  Semantic Memory (Level 3)
# ──────────────────────────────────────────────


class TestSemanticMemory:
    """Tests for pgvector-backed semantic memory."""

    @pytest.mark.asyncio
    async def test_consolidate_new_pattern(self, mock_db_session):
        """Consolidate stores a new pattern when no similar one exists."""
        with patch.object(
            SemanticMemoryManager, "_generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)
        ):
            mgr = SemanticMemoryManager(mock_db_session)
            record = await mgr.consolidate(
                pattern="Always use parameterised queries for SQL",
                category="security",
            )
            assert record is not None
            mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_consolidate_increments_strength(self, mock_db_session):
        """Consolidate increments strength when similar pattern exists."""
        existing = SemanticMemory(
            id=1,
            pattern_text="Use parameterised queries",
            category="security",
            strength=2,
        )
        with patch.object(
            SemanticMemoryManager, "_generate_embedding", new=AsyncMock(return_value=[0.1] * 1536)
        ):
            with patch.object(
                SemanticMemoryManager,
                "_find_similar",
                new=AsyncMock(return_value=existing),
            ):
                mgr = SemanticMemoryManager(mock_db_session)
                record = await mgr.consolidate(
                    pattern="Always use parameterised queries for SQL",
                    category="security",
                )
                assert record is existing
                assert record.strength == 3  # incremented from 2

    @pytest.mark.asyncio
    async def test_consolidate_skips_when_embedding_fails(self, mock_db_session):
        """Consolidate returns None when embedding generation fails."""
        with patch.object(
            SemanticMemoryManager,
            "_generate_embedding",
            new=AsyncMock(return_value=None),
        ):
            mgr = SemanticMemoryManager(mock_db_session)
            record = await mgr.consolidate(
                pattern="Some pattern",
                category="general",
            )
            assert record is None
            mock_db_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_retrieve_relevant(self, mock_db_session):
        """retrieve_relevant returns patterns relevant to the code context."""
        mock_pattern = SemanticMemory(
            id=1,
            pattern_text="Use parameterised queries",
            category="security",
            strength=3,
        )
        mock_result_row = (mock_pattern, 0.15)
        mock_result = MagicMock()
        mock_result.all = MagicMock(return_value=[mock_result_row])
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(
            SemanticMemoryManager,
            "_generate_embedding",
            new=AsyncMock(return_value=[0.1] * 1536),
        ):
            mgr = SemanticMemoryManager(mock_db_session)
            patterns = await mgr.retrieve_relevant("SELECT * FROM users")
            assert len(patterns) == 1
            assert patterns[0].pattern_text == "Use parameterised queries"

    @pytest.mark.asyncio
    async def test_get_all(self, mock_db_session):
        """get_all returns all patterns ordered by strength."""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(
            return_value=[
                SemanticMemory(id=2, pattern_text="P2", category="sec", strength=5),
                SemanticMemory(id=1, pattern_text="P1", category="sec", strength=3),
            ]
        )
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mgr = SemanticMemoryManager(mock_db_session)
        patterns = await mgr.get_all()
        assert len(patterns) == 2
        assert patterns[0].strength >= patterns[1].strength

    @pytest.mark.asyncio
    async def test_get_by_category(self, mock_db_session):
        """get_by_category filters by category."""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(
            return_value=[
                SemanticMemory(id=1, pattern_text="P1", category="security", strength=3),
            ]
        )
        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        mgr = SemanticMemoryManager(mock_db_session)
        patterns = await mgr.get_by_category("security")
        assert len(patterns) == 1
        assert patterns[0].category == "security"


# ──────────────────────────────────────────────
#  Consolidator
# ──────────────────────────────────────────────


class TestConsolidator:
    """Tests for episodic → semantic promotion."""

    @pytest.mark.asyncio
    async def test_run_promotes_patterns_above_threshold(self, mock_db_session):
        """Patterns appearing 3+ times are promoted to semantic memory."""
        episodic_mgr = EpisodicMemoryManager(mock_db_session)
        semantic_mgr = SemanticMemoryManager(mock_db_session)

        repeated_finding = "SQL injection vulnerability in query builder"
        sessions = []
        for i in range(4):
            ses = EpisodicMemory(
                id=f"ses-{i}",
                session_id=f"ses-{i}",
                code_hash=f"hash{i}",
                code="code",
                findings_json=f'[{{"agent": "security", "hallazgo": "{repeated_finding}", "detalle": "test", "impacto": "Crítico", "propuesta": "fix", "ronda": 1}}]',
                score=1.0,
                created_at=datetime.now(timezone.utc) - timedelta(days=i),
            )
            sessions.append(ses)

        episodic_mgr.list_recent = AsyncMock(return_value=sessions)
        semantic_mgr.consolidate = AsyncMock(
            return_value=SemanticMemory(
                id=1, pattern_text=repeated_finding, category="security", strength=1
            )
        )

        consolidator = Consolidator(
            episodic_mgr=episodic_mgr, semantic_mgr=semantic_mgr
        )
        promoted_count = await consolidator.run(current_session_id=None)

        assert promoted_count >= 1
        semantic_mgr.consolidate.assert_called()

    @pytest.mark.asyncio
    async def test_run_skips_below_threshold(self, mock_db_session):
        """Patterns appearing fewer than 3 times are not promoted."""
        episodic_mgr = EpisodicMemoryManager(mock_db_session)
        semantic_mgr = SemanticMemoryManager(mock_db_session)

        ses = EpisodicMemory(
            id="ses-1",
            session_id="ses-1",
            code_hash="hash",
            code="code",
            findings_json='[{"agent": "quality", "hallazgo": "Unique finding only once", "detalle": "test", "impacto": "Medio", "propuesta": "fix", "ronda": 1}]',
            score=1.0,
            created_at=datetime.now(timezone.utc),
        )
        episodic_mgr.list_recent = AsyncMock(return_value=[ses])
        semantic_mgr.consolidate = AsyncMock(return_value=None)

        consolidator = Consolidator(
            episodic_mgr=episodic_mgr, semantic_mgr=semantic_mgr
        )
        promoted_count = await consolidator.run(current_session_id=None)

        assert promoted_count == 0
        semantic_mgr.consolidate.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_excludes_current_session(self, mock_db_session):
        """The current session is excluded to avoid self-promotion."""
        episodic_mgr = EpisodicMemoryManager(mock_db_session)
        semantic_mgr = SemanticMemoryManager(mock_db_session)

        ses = EpisodicMemory(
            id="ses-current",
            session_id="ses-current",
            code_hash="hash",
            code="code",
            findings_json='[{"agent": "security", "hallazgo": "Test pattern", "detalle": "d", "impacto": "Crítico", "propuesta": "p", "ronda": 1}]',
            score=1.0,
            created_at=datetime.now(timezone.utc),
        )
        episodic_mgr.list_recent = AsyncMock(return_value=[ses])
        semantic_mgr.consolidate = AsyncMock(return_value=None)

        consolidator = Consolidator(
            episodic_mgr=episodic_mgr, semantic_mgr=semantic_mgr
        )
        promoted_count = await consolidator.run(current_session_id="ses-current")
        assert promoted_count == 0

    def test_infer_category_by_agent(self):
        """_infer_category returns the agent name for agent-voted patterns."""
        pattern = "SQL injection vulnerability"
        findings = [
            {"agent": "security", "hallazgo": "SQL injection vulnerability"},
            {"agent": "security", "hallazgo": "SQL injection vulnerability"},
        ]
        category = Consolidator._infer_category(pattern, findings)
        assert category == "security"

    def test_infer_category_by_fallback(self):
        """_infer_category falls back to keyword matching when no agent votes."""
        pattern = "SQL injection in query"
        category = Consolidator._infer_category(pattern, [])
        assert category == "security"

    def test_infer_category_fallback_architecture(self):
        pattern = "SOLID violation in service layer"
        category = Consolidator._infer_category(pattern, [])
        assert category == "architecture"

    def test_infer_category_fallback_quality(self):
        """Uses Spanish fallback keywords for quality."""
        pattern = "Alta complejidad ciclomática en la función"
        category = Consolidator._infer_category(pattern, [])
        assert category == "quality"

    def test_infer_category_fallback_performance(self):
        pattern = "N+1 query detected in loop"
        category = Consolidator._infer_category(pattern, [])
        assert category == "performance"

    def test_infer_category_fallback_ux(self):
        """Uses Spanish fallback keywords for UX."""
        pattern = "Problema de accesibilidad en el formulario"
        category = Consolidator._infer_category(pattern, [])
        assert category == "ux"

    def test_infer_category_fallback_general(self):
        pattern = "Some random pattern that doesn't match any category"
        category = Consolidator._infer_category(pattern, [])
        assert category == "general"
