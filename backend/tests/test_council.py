"""Tests for the council orchestrator, protocol, and synthesizer."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.council.orchestrator import CouncilOrchestrator
from backend.council.protocol import (
    add_dado_nuevo,
    format_finding,
    format_findings_list,
    format_round_header,
    parse_finding,
)
from backend.council.synthesizer import synthesize, _cluster_findings, _text_similarity
from backend.models.schemas import ConsolidatedFinding, Finding, Report


# ──────────────────────────────────────────────
#  Synthesizer tests
# ──────────────────────────────────────────────

# Synthesize is async (calls LLM for narrative). We mock the LLM part
# so unit tests don't need a real API key.
_NARRATIVE_MOCK = {
    "summary": "Code review complete: findings identified.",
    "risk_overview": "No risks identified.",
    "detailed_review": "All agents analysed the code.",
    "remediation_roadmap": "No remediation required.",
}


@pytest.mark.asyncio
async def test_synthesize_empty_findings():
    """Synthesizing with no findings returns a report with empty list."""
    report = await synthesize({1: [], 2: [], 3: []})
    assert isinstance(report, Report)
    assert report.findings == []


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_uses_round_3_when_available(mock_gn):
    """Synthesis should prefer Round 3 findings over earlier rounds."""
    r1 = [Finding(agent="a", title="finding1", detail="d", impact="High", proposal="p", round_num=1)]
    r3 = [Finding(agent="a", title="finding2", detail="d", impact="Critical", proposal="p", round_num=3)]
    report = await synthesize({1: r1, 2: [], 3: r3})
    # Round 3 findings should be used
    assert len(report.findings) > 0
    assert report.findings[0].title == "finding2"


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_fallback_to_round_2(mock_gn):
    """Synthesis falls back to Round 2 when Round 3 is empty."""
    r1 = [Finding(agent="a", title="finding1", detail="d", impact="High", proposal="p", round_num=1)]
    r2 = [Finding(agent="b", title="finding2", detail="d", impact="Medium", proposal="p", round_num=2)]
    report = await synthesize({1: r1, 2: r2})
    assert len(report.findings) > 0
    assert report.findings[0].title == "finding2"


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_fallback_to_round_1(mock_gn):
    """Synthesis falls back to Round 1 when Rounds 2 and 3 are empty."""
    r1 = [Finding(agent="a", title="finding1", detail="d", impact="High", proposal="p", round_num=1)]
    report = await synthesize({1: r1, 2: [], 3: []})
    assert len(report.findings) > 0
    assert report.findings[0].title == "finding1"


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_clusters_similar_findings(mock_gn):
    """Two similar findings from different agents should be clustered."""
    findings = [
        Finding(agent="security", title="SQL injection vulnerability", detail="Line 5", impact="Critical", proposal="Use params", round_num=3),
        Finding(agent="architecture", title="SQL injection in query", detail="Line 5-6", impact="High", proposal="Use ORM", round_num=3),
    ]
    report = await synthesize({3: findings})
    assert len(report.findings) == 1  # clustered together
    cf = report.findings[0]
    assert cf.consensus_score > 0
    assert len(cf.votes) == 2  # both agents voted


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_separates_dissimilar_findings(mock_gn):
    """Dissimilar findings should remain separate."""
    findings = [
        Finding(agent="security", title="SQL injection vulnerability", detail="Line 5", impact="Critical", proposal="Use params", round_num=3),
        Finding(agent="ux", title="Missing aria labels on buttons", detail="Line 20", impact="Low", proposal="Add aria-label", round_num=3),
    ]
    report = await synthesize({3: findings})
    assert len(report.findings) == 2


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_consensus_score_all_agree(mock_gn):
    """When 5 of 6 agents vote on a finding, consensus score should be 5/6 ~ 0.83."""
    findings = [
        Finding(agent="security", title="SQL injection", detail="d", impact="Critical", proposal="p", round_num=3),
        Finding(agent="architecture", title="SQL injection", detail="d", impact="High", proposal="p", round_num=3),
        Finding(agent="quality", title="SQL injection", detail="d", impact="High", proposal="p", round_num=3),
        Finding(agent="performance", title="SQL injection", detail="d", impact="Medium", proposal="p", round_num=3),
        Finding(agent="ux", title="SQL injection", detail="d", impact="Medium", proposal="p", round_num=3),
    ]
    report = await synthesize({3: findings})
    assert len(report.findings) == 1
    assert report.findings[0].consensus_score == pytest.approx(5 / 6, rel=0.01)
    assert report.findings[0].consensus_level == "High"


@pytest.mark.asyncio
@patch("backend.council.synthesizer._generate_narrative", return_value=_NARRATIVE_MOCK)
async def test_synthesize_summary_counts(mock_gn):
    """The executive summary should correctly count findings by severity."""
    findings = [
        Finding(agent="a", title="Critical bug", detail="d", impact="Critical", proposal="p", round_num=3),
        Finding(agent="b", title="High issue", detail="d", impact="High", proposal="p", round_num=3),
        Finding(agent="c", title="Medium thing", detail="d", impact="Medium", proposal="p", round_num=3),
    ]
    report = await synthesize({3: findings})
    assert "findings identified" in report.summary or "3" in report.summary
    assert report.findings[0].impact == "Critical"


def test_text_similarity():
    """Similar texts produce a score > 0.35 threshold."""
    sim = _text_similarity("SQL injection vulnerability", "SQL injection in query")
    assert sim > 0.35


def test_text_similarity_dissimilar():
    """Dissimilar texts produce a score < 0.35 threshold."""
    sim = _text_similarity("SQL injection", "Missing aria labels")
    assert sim < 0.35


# ──────────────────────────────────────────────
#  Protocol tests
# ──────────────────────────────────────────────


def test_format_finding():
    """format_finding produces the expected Inverted Pyramid string."""
    f = Finding(agent="security", title="Test finding", detail="Detail text", impact="High", proposal="Fix it", round_num=1)
    result = format_finding(f)
    assert "FINDING: Test finding" in result
    assert "··· Detail: Detail text" in result
    assert "··· Impact: High" in result
    assert "··· Proposal: Fix it" in result


def test_format_finding_with_agent():
    """format_finding with include_agent=True prepends the agent name."""
    f = Finding(agent="security", title="Test", detail="D", impact="High", proposal="P", round_num=1)
    result = format_finding(f, include_agent=True)
    assert result.startswith("[security]")


def test_format_findings_list():
    """format_findings_list joins multiple findings with blank lines."""
    f1 = Finding(agent="a", title="F1", detail="D1", impact="High", proposal="P1", round_num=1)
    f2 = Finding(agent="b", title="F2", detail="D2", impact="Medium", proposal="P2", round_num=1)
    result = format_findings_list([f1, f2])
    assert "FINDING: F1" in result
    assert "FINDING: F2" in result
    assert "\n\n" in result  # separated by blank line


def test_format_round_header():
    """Round headers have the expected format."""
    r1 = format_round_header(1)
    assert "ROUND 1" in r1
    assert "Analysis" in r1 or "Individual" in r1
    r2 = format_round_header(2)
    assert "ROUND 2" in r2
    r3 = format_round_header(3)
    assert "ROUND 3" in r3
    assert isinstance(format_round_header(99), str)


def test_parse_finding():
    """parse_finding extracts fields from a well-formed Inverted Pyramid block."""
    text = (
        "[security]\n"
        "FINDING: SQL injection\n"
        "··· Detail: Unsanitized input\n"
        "··· Impact: Critical\n"
        "··· Proposal: Use params"
    )
    f = parse_finding(text)
    assert f is not None
    assert f.agent == "security"
    assert f.title == "SQL injection"
    assert f.detail == "Unsanitized input"
    assert f.proposal == "Use params"


def test_parse_finding_no_agent_prefix():
    """parse_finding works even without an [agent] prefix."""
    text = (
        "FINDING: SQL injection\n"
        "··· Detail: Unsanitized input\n"
        "··· Impact: Critical\n"
        "··· Proposal: Use params"
    )
    f = parse_finding(text)
    assert f is not None
    assert f.agent == "unknown"
    assert f.title == "SQL injection"


def test_parse_finding_invalid_returns_none():
    """parse_finding returns None when no FINDING is found."""
    text = "Some random text without proper format"
    f = parse_finding(text)
    assert f is None


def test_add_dado_nuevo_with_context():
    """add_dado_nuevo creates a Given-New prefix when there are previous findings."""
    prev = [
        Finding(agent="architecture", title="Poor separation of concerns", detail="D", impact="High", proposal="P", round_num=1),
    ]
    my = Finding(agent="security", title="SQL injection in query", detail="D", impact="Critical", proposal="P", round_num=2)
    result = add_dado_nuevo(prev, my)
    assert "Agreeing with" in result
    assert "[architecture]" in result


def test_add_dado_nuevo_no_context():
    """add_dado_nuevo returns the title as-is when there are no previous findings."""
    my = Finding(agent="security", title="SQL injection", detail="D", impact="Critical", proposal="P", round_num=1)
    result = add_dado_nuevo([], my)
    assert result == "SQL injection"


# ──────────────────────────────────────────────
#  Orchestrator tests
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_creates_session_id_when_none_given(mock_async_session_factory, mock_agents):
    """Orchestrator generates a session ID when none is provided."""
    orch = CouncilOrchestrator()
    # Replace real agents with mocks
    orch.agents = mock_agents

    report, session_id, round_data = await orch.run_council(
        code="def foo(): pass", session_id=None
    )
    assert session_id is not None
    assert session_id.startswith("ses-")


@pytest.mark.asyncio
async def test_orchestrator_uses_provided_session_id(mock_async_session_factory, mock_agents):
    """Orchestrator uses the provided session ID."""
    orch = CouncilOrchestrator()
    orch.agents = mock_agents

    report, session_id, round_data = await orch.run_council(
        code="def foo(): pass", session_id="ses-custom123"
    )
    assert session_id == "ses-custom123"


@pytest.mark.asyncio
async def test_orchestrator_three_rounds_execute(mock_async_session_factory, mock_agents):
    """All three rounds are executed and findings are stored."""
    orch = CouncilOrchestrator()
    orch.agents = mock_agents

    report, session_id, round_data = await orch.run_council(
        code="def foo(): pass", session_id=None
    )

    assert "round_1" in round_data
    assert "round_2" in round_data
    assert "round_3" in round_data
    assert "report" in round_data


@pytest.mark.asyncio
async def test_orchestrator_each_agent_called_per_round(mock_async_session_factory, mock_agents):
    """Each agent's analyze is called exactly once per round (3 times total)."""
    orch = CouncilOrchestrator()
    orch.agents = mock_agents

    await orch.run_council(code="def foo(): pass", session_id=None)

    for name, agent in mock_agents.items():
        assert agent.analyze.await_count == 3, (
            f"{name} was called {agent.analyze.await_count} times, expected 3"
        )


@pytest.mark.asyncio
async def test_orchestrator_synthesis_produces_report(mock_async_session_factory, mock_agents):
    """The final synthesis produces a Report with findings."""
    orch = CouncilOrchestrator()
    orch.agents = mock_agents

    report, session_id, round_data = await orch.run_council(
        code="def foo(): pass", session_id=None
    )

    assert isinstance(report, Report)
    assert len(report.findings) > 0


@pytest.mark.asyncio
async def test_orchestrator_working_memory_updated(mock_async_session_factory, mock_agents):
    """Working memory is updated after each round."""
    orch = CouncilOrchestrator()
    orch.agents = mock_agents

    report, session_id, round_data = await orch.run_council(
        code="def foo(): pass", session_id="ses-test123"
    )

    stored = orch.working_memory.get("ses-test123")
    assert stored is not None
    assert stored["status"] == "completed"


@pytest.mark.asyncio
async def test_orchestrator_empty_code_handling(mock_async_session_factory):
    """When all agents return no findings, the report is still valid."""
    # Configure agents to return empty findings
    agents = {}
    for name in ("security", "architecture", "quality", "performance", "ux"):
        agent = MagicMock()
        agent.name = name
        agent.analyze = AsyncMock(return_value=[])
        agents[name] = agent

    orch = CouncilOrchestrator()
    orch.agents = agents

    report, session_id, round_data = await orch.run_council(
        code="", session_id=None
    )

    assert isinstance(report, Report)
    # Report should have no findings
    assert len(report.findings) == 0


# ──────────────────────────────────────────────
#  Orchestrator error handling
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_orchestrator_agent_failure_doesnt_crash(mock_async_session_factory):
    """If one agent fails, the others still produce results."""
    agents = {}
    for name in ("security", "architecture", "quality", "performance", "ux"):
        agent = MagicMock()
        agent.name = name
        if name == "security":
            agent.analyze = AsyncMock(side_effect=RuntimeError("API failure"))
        else:
            agent.analyze = AsyncMock(
                return_value=[
                    Finding(
                        agent=name,
                        title=f"{name} finding",
                        detail="detail",
                        impact="Medium",
                        proposal="fix",
                        round_num=1,
                    )
                ]
            )
        agents[name] = agent

    orch = CouncilOrchestrator()
    orch.agents = agents

    report, session_id, round_data = await orch.run_council(
        code="def foo(): pass", session_id=None
    )

    assert isinstance(report, Report)
    # The 4 non-failing agents should have contributed
    assert len(report.findings) > 0
