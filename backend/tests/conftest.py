"""Shared fixtures, mocks, and test data for Qwen Council tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

# Set fake API key so the OpenAI SDK doesn't raise at client instantiation
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-tests")

# Ensure the backend package is importable (add project root to sys.path)
_project_root = str(Path(__file__).resolve().parent.parent.parent)  # backend/.. -> project root
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.models.schemas import Finding


# ──────────────────────────────────────────────
#  Test Data
# ──────────────────────────────────────────────

SAMPLE_CODE_VULNERABLE = """
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()
"""

SAMPLE_CODE_CLEAN = """
def add(a: int, b: int) -> int:
    return a + b
"""

SAMPLE_FINDING_TEXT = (
    "FINDING: SQL injection vulnerability in get_user function\n"
    '··· Detail: Line 6: query = f"SELECT * FROM users WHERE id = {user_id}" — user_id is unsanitized\n'
    "··· Impact: Critical\n"
    "··· Proposal: Use parameterised queries instead of f-string interpolation"
)

SAMPLE_FINDING_TEXT_NO_FINDINGS = "NO_FINDINGS"

SAMPLE_GIVEN_NEW_TEXT = (
    "Agreeing with [security] on SQL injection vulnerability, I add that:\n"
    "FINDING: Parameter validation should also be added\n"
    "··· Detail: user_id should be validated as integer\n"
    "··· Impact: High\n"
    "··· Proposal: Add isinstance check and range validation"
)

SAMPLE_ROUND3_TEXT = (
    "KEEP:\n"
    "FINDING: SQL injection vulnerability in get_user function\n"
    "··· Detail: See above\n"
    "··· Impact: Critical\n"
    "··· Proposal: Use parameterised queries"
)


# ──────────────────────────────────────────────
#  Factory helpers
# ──────────────────────────────────────────────

def make_finding(
    agent: str = "security",
    title: str = "Test finding",
    detail: str = "Test detail with evidence",
    impact: str = "Medium",
    proposal: str = "Test fix proposal",
    round_num: int = 1,
) -> Finding:
    """Create a Finding with sensible defaults."""
    return Finding(
        agent=agent,
        title=title,
        detail=detail,
        impact=impact,
        proposal=proposal,
        round_num=round_num,
    )


def make_finding_dict(
    agent: str = "security",
    title: str = "Test finding",
    detail: str = "Test detail",
    impact: str = "Medium",
    proposal: str = "Test fix",
    round_num: int = 1,
) -> dict:
    """Create a finding dict (as stored in episodic memory)."""
    return {
        "agent": agent,
        "title": title,
        "detail": detail,
        "impact": impact,
        "proposal": proposal,
        "round_num": round_num,
    }


# ──────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def mock_qwen_client():
    """Mock the underlying AsyncOpenAI client so tests never call the real API.

    Returns the mock client instance so callers can configure return values.
    """
    with patch("backend.agents.base_agent.AsyncOpenAI") as mock_cls:
        client_instance = MagicMock()
        mock_cls.return_value = client_instance

        # chat.completions.create -> return a response with the finding text
        mock_chat_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = SAMPLE_FINDING_TEXT
        mock_choice.message = mock_message
        mock_chat_response.choices = [mock_choice]
        client_instance.chat.completions.create = AsyncMock(
            return_value=mock_chat_response
        )

        # embeddings.create -> return a mock embedding
        mock_embed_response = MagicMock()
        mock_embed_data = MagicMock()
        mock_embed_data.embedding = [0.1] * 1536
        mock_embed_response.data = [mock_embed_data]
        client_instance.embeddings.create = AsyncMock(
            return_value=mock_embed_response
        )

        yield client_instance


@pytest.fixture
def mock_qwen_client_no_findings():
    """Mock the LLM to return NO_FINDINGS."""
    with patch("backend.agents.base_agent.AsyncOpenAI") as mock_cls:
        client_instance = MagicMock()
        mock_cls.return_value = client_instance

        mock_chat_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = SAMPLE_FINDING_TEXT_NO_FINDINGS
        mock_choice.message = mock_message
        mock_chat_response.choices = [mock_choice]
        client_instance.chat.completions.create = AsyncMock(
            return_value=mock_chat_response
        )

        yield client_instance


@pytest.fixture
def mock_qwen_client_given_new():
    """Mock the LLM to return a Given-New style response."""
    with patch("backend.agents.base_agent.AsyncOpenAI") as mock_cls:
        client_instance = MagicMock()
        mock_cls.return_value = client_instance

        mock_chat_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = SAMPLE_GIVEN_NEW_TEXT
        mock_choice.message = mock_message
        mock_chat_response.choices = [mock_choice]
        client_instance.chat.completions.create = AsyncMock(
            return_value=mock_chat_response
        )

        yield client_instance


@pytest.fixture
def mock_db_session():
    """Create a mock AsyncSession with minimal surface for memory tests."""
    session = AsyncMock()
    # Mock the async context manager for `async with session.begin()`
    session.begin = AsyncMock(return_value=session)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    # execute returns an empty result by default
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_result.scalars = MagicMock(return_value=MagicMock())
    mock_result.scalars.return_value.all = MagicMock(return_value=[])
    mock_result.all = MagicMock(return_value=[])
    mock_result.scalar_one = MagicMock(return_value=0.5)
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_async_session_factory(mock_db_session):
    """Mock async_session_factory so orchestrator gets a fake DB session."""
    with patch("backend.council.orchestrator.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(
            return_value=mock_db_session
        )
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock_factory


@pytest.fixture
def sample_findings_round1():
    """Return a dict of agent -> [Finding] simulating Round 1 output."""
    return {
        "security": [
            make_finding(
                agent="security",
                title="SQL injection via string interpolation",
                detail="Line 6: unsanitized f-string in query",
                impact="Critical",
                proposal="Use parameterised queries",
                round_num=1,
            )
        ],
        "architecture": [
            make_finding(
                agent="architecture",
                title="No separation of concerns",
                detail="Database access mixed with business logic in get_user",
                impact="High",
                proposal="Extract DB layer to repository pattern",
                round_num=1,
            )
        ],
        "quality": [],
        "performance": [],
        "ux": [],
    }


@pytest.fixture
def sample_findings_round2():
    """Simulate Round 2 agent output with Given-New cross-references."""
    return {
        "security": [
            make_finding(
                agent="security",
                title="Agreeing with [architecture], SQL injection is critical",
                detail="Parameter validation also needed",
                impact="Critical",
                proposal="Use parameterised queries and input validation",
                round_num=2,
            )
        ],
        "architecture": [
            make_finding(
                agent="architecture",
                title="Building on [security], use an ORM layer",
                detail="SQLAlchemy would prevent raw SQL injection",
                impact="High",
                proposal="Replace raw sqlite3 with SQLAlchemy ORM",
                round_num=2,
            )
        ],
        "quality": [],
        "performance": [],
        "ux": [],
    }


@pytest.fixture
def sample_findings_round3():
    """Simulate Round 3 agent output with KEEP/MODIFY/WITHDRAW."""
    return {
        "security": [
            make_finding(
                agent="security",
                title="KEEP: SQL injection via string interpolation",
                detail="Confirmed by all agents",
                impact="Critical",
                proposal="Use parameterised queries",
                round_num=3,
            )
        ],
        "architecture": [
            make_finding(
                agent="architecture",
                title="MODIFY: Use SQLAlchemy ORM instead of raw sqlite3",
                detail="Addresses both security and architecture concerns",
                impact="High",
                proposal="Migrate to SQLAlchemy ORM",
                round_num=3,
            )
        ],
        "quality": [],
        "performance": [],
        "ux": [],
    }


@pytest.fixture
def mock_agents(sample_findings_round1, sample_findings_round2, sample_findings_round3):
    """Create mock agent instances that return predefined findings per round.

    Returns a dict of agent_name -> MagicMock suitable for injection
    into the orchestrator.
    """
    round_map = {1: sample_findings_round1, 2: sample_findings_round2, 3: sample_findings_round3}
    agents = {}
    for name in ("security", "architecture", "quality", "performance", "ux"):
        agent = MagicMock()
        agent.name = name

        async def _analyze(code="", context=None, round=1, _name=name):
            return round_map.get(round, {}).get(_name, [])

        agent.analyze = AsyncMock(side_effect=_analyze)
        agents[name] = agent
    return agents
