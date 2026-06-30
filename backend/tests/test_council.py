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


def test_synthesize_empty_findings():
    """Synthesizing with no findings returns a report with empty list."""
    report = synthesize({1: [], 2: [], 3: []})
    assert isinstance(report, Report)
    assert report.findings == []


def test_synthesize_uses_round_3_when_available():
    """Synthesis should prefer Round 3 findings over earlier rounds."""
    r1 = [Finding(agent="a", hallazgo="finding1", detalle="d", impacto="Alto", propuesta="p", ronda=1)]
    r3 = [Finding(agent="a", hallazgo="finding2", detalle="d", impacto="Crítico", propuesta="p", ronda=3)]
    report = synthesize({1: r1, 2: [], 3: r3})
    # Round 3 findings should be used
    assert len(report.findings) > 0
    assert report.findings[0].hallazgo == "finding2"


def test_synthesize_fallback_to_round_2():
    """Synthesis falls back to Round 2 when Round 3 is empty."""
    r1 = [Finding(agent="a", hallazgo="finding1", detalle="d", impacto="Alto", propuesta="p", ronda=1)]
    r2 = [Finding(agent="b", hallazgo="finding2", detalle="d", impacto="Medio", propuesta="p", ronda=2)]
    report = synthesize({1: r1, 2: r2})
    assert len(report.findings) > 0
    assert report.findings[0].hallazgo == "finding2"


def test_synthesize_fallback_to_round_1():
    """Synthesis falls back to Round 1 when Rounds 2 and 3 are empty."""
    r1 = [Finding(agent="a", hallazgo="finding1", detalle="d", impacto="Alto", propuesta="p", ronda=1)]
    report = synthesize({1: r1, 2: [], 3: []})
    assert len(report.findings) > 0
    assert report.findings[0].hallazgo == "finding1"


def test_synthesize_clusters_similar_findings():
    """Two similar findings from different agents should be clustered."""
    findings = [
        Finding(agent="security", hallazgo="SQL injection vulnerability", detalle="Line 5", impacto="Crítico", propuesta="Use params", ronda=3),
        Finding(agent="architecture", hallazgo="SQL injection in query", detalle="Line 5-6", impacto="Alto", propuesta="Use ORM", ronda=3),
    ]
    report = synthesize({3: findings})
    assert len(report.findings) == 1  # clustered together
    cf = report.findings[0]
    assert cf.consensus_score > 0
    assert len(cf.votes) == 2  # both agents voted


def test_synthesize_separates_dissimilar_findings():
    """Dissimilar findings should remain separate."""
    findings = [
        Finding(agent="security", hallazgo="SQL injection vulnerability", detalle="Line 5", impacto="Crítico", propuesta="Use params", ronda=3),
        Finding(agent="ux", hallazgo="Missing aria labels on buttons", detalle="Line 20", impacto="Bajo", propuesta="Add aria-label", ronda=3),
    ]
    report = synthesize({3: findings})
    assert len(report.findings) == 2


def test_synthesize_consensus_score_all_agree():
    """When all 5 agents vote on a finding, consensus score should be 1.0."""
    findings = [
        Finding(agent="security", hallazgo="SQL injection", detalle="d", impacto="Crítico", propuesta="p", ronda=3),
        Finding(agent="architecture", hallazgo="SQL injection", detalle="d", impacto="Alto", propuesta="p", ronda=3),
        Finding(agent="quality", hallazgo="SQL injection", detalle="d", impacto="Alto", propuesta="p", ronda=3),
        Finding(agent="performance", hallazgo="SQL injection", detalle="d", impacto="Medio", propuesta="p", ronda=3),
        Finding(agent="ux", hallazgo="SQL injection", detalle="d", impacto="Medio", propuesta="p", ronda=3),
    ]
    report = synthesize({3: findings})
    assert len(report.findings) == 1
    assert report.findings[0].consensus_score == 1.0
    assert report.findings[0].consensus_level == "Alto"


def test_synthesize_summary_counts():
    """The executive summary should correctly count findings by severity."""
    findings = [
        Finding(agent="a", hallazgo="Critical bug", detalle="d", impacto="Crítico", propuesta="p", ronda=3),
        Finding(agent="b", hallazgo="High issue", detalle="d", impacto="Alto", propuesta="p", ronda=3),
        Finding(agent="c", hallazgo="Medium thing", detalle="d", impacto="Medio", propuesta="p", ronda=3),
    ]
    report = synthesize({3: findings})
    assert "3 hallazgos" in report.summary
    assert "1 críticos" in report.summary or "1 crítico" in report.summary


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
    f = Finding(agent="security", hallazgo="Test finding", detalle="Detail text", impacto="High", propuesta="Fix it", ronda=1)
    result = format_finding(f)
    assert "HALLAZGO: Test finding" in result
    assert "··· Detalle: Detail text" in result
    assert "··· Impacto: High" in result
    assert "··· Propuesta: Fix it" in result


def test_format_finding_with_agent():
    """format_finding with include_agent=True prepends the agent name."""
    f = Finding(agent="security", hallazgo="Test", detalle="D", impacto="High", propuesta="P", ronda=1)
    result = format_finding(f, include_agent=True)
    assert result.startswith("[security]")


def test_format_findings_list():
    """format_findings_list joins multiple findings with blank lines."""
    f1 = Finding(agent="a", hallazgo="F1", detalle="D1", impacto="High", propuesta="P1", ronda=1)
    f2 = Finding(agent="b", hallazgo="F2", detalle="D2", impacto="Medium", propuesta="P2", ronda=1)
    result = format_findings_list([f1, f2])
    assert "HALLAZGO: F1" in result
    assert "HALLAZGO: F2" in result
    assert "\n\n" in result  # separated by blank line


def test_format_round_header():
    """Round headers have the expected format."""
    r1 = format_round_header(1)
    assert "RONDA 1" in r1
    assert "Análisis" in r1 or "Individual" in r1
    r2 = format_round_header(2)
    assert "RONDA 2" in r2
    r3 = format_round_header(3)
    assert "RONDA 3" in r3
    assert isinstance(format_round_header(99), str)


def test_parse_finding():
    """parse_finding extracts fields from a well-formed Inverted Pyramid block."""
    text = (
        "[security]\n"
        "HALLAZGO: SQL injection\n"
        "··· Detalle: Unsanitized input\n"
        "··· Impacto: Crítico\n"
        "··· Propuesta: Use params"
    )
    f = parse_finding(text)
    assert f is not None
    assert f.agent == "security"
    assert f.hallazgo == "SQL injection"
    assert f.detalle == "Unsanitized input"
    assert f.propuesta == "Use params"


def test_parse_finding_no_agent_prefix():
    """parse_finding works even without an [agent] prefix."""
    text = (
        "HALLAZGO: SQL injection\n"
        "··· Detalle: Unsanitized input\n"
        "··· Impacto: Crítico\n"
        "··· Propuesta: Use params"
    )
    f = parse_finding(text)
    assert f is not None
    assert f.agent == "unknown"
    assert f.hallazgo == "SQL injection"


def test_parse_finding_invalid_returns_none():
    """parse_finding returns None when no HALLAZGO is found."""
    text = "Some random text without proper format"
    f = parse_finding(text)
    assert f is None


def test_add_dado_nuevo_with_context():
    """add_dado_nuevo creates a Given-New prefix when there are previous findings."""
    prev = [
        Finding(agent="architecture", hallazgo="Poor separation of concerns", detalle="D", impacto="High", propuesta="P", ronda=1),
    ]
    my = Finding(agent="security", hallazgo="SQL injection in query", detalle="D", impacto="Critical", propuesta="P", ronda=2)
    result = add_dado_nuevo(prev, my)
    assert "Coincidiendo con" in result
    assert "[architecture]" in result


def test_add_dado_nuevo_no_context():
    """add_dado_nuevo returns the hallazgo as-is when there are no previous findings."""
    my = Finding(agent="security", hallazgo="SQL injection", detalle="D", impacto="Critical", propuesta="P", ronda=1)
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
                        hallazgo=f"{name} finding",
                        detalle="detail",
                        impacto="Medium",
                        propuesta="fix",
                        ronda=1,
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
