"""Protocol formatters for the Inverted Pyramid and Given-New communication pattern.

Every message between agents follows the Inverted Pyramid structure:
  FINDING + ··· Detail + ··· Impact + ··· Proposal
"""

from __future__ import annotations

import re
from typing import Any

from backend.models.schemas import Finding


# ──────────────────────────────────────────────
#  Formatting
# ──────────────────────────────────────────────


def format_finding(finding: Finding, include_agent: bool = False) -> str:
    """Convert a Finding to its Inverted Pyramid string representation.

    Parameters
    ----------
    finding : Finding
        The finding to format.
    include_agent : bool
        Prepend the agent name.

    Returns
    -------
    str
        Formatted finding string.
    """
    parts: list[str] = []
    if include_agent:
        parts.append(f"[{finding.agent}]")
    parts.append(f"FINDING: {finding.title}")
    parts.append(f"··· Detail: {finding.detail}")
    parts.append(f"··· Impact: {finding.impact}")
    parts.append(f"··· Proposal: {finding.proposal}")
    return "\n".join(parts)


def format_findings_list(
    findings: list[Finding], include_agent: bool = False
) -> str:
    """Format multiple findings separated by blank lines."""
    return "\n\n".join(
        format_finding(f, include_agent=include_agent) for f in findings
    )


def format_round_header(round: int) -> str:
    """Return a header string for a given round."""
    titles = {
        1: "═══ ROUND 1: Individual Analysis ═══",
        2: "═══ ROUND 2: Cross Debate (Given-New) ═══",
        3: "═══ ROUND 3: Final Refinement ═══",
    }
    return titles.get(round, f"═══ Round {round} ═══")


# ──────────────────────────────────────────────
#  Given-New prefix builder
# ──────────────────────────────────────────────


def add_dado_nuevo(
    previous_findings: list[Finding], my_finding: Finding
) -> str:
    """Build a Dado-Nuevo (Given-New) prefix for a finding.

    The prefix references a previous finding from another agent to create
    explicit cross-references (cohesion).

    Parameters
    ----------
    previous_findings : list[Finding]
        Findings from other agents in the previous round.
    my_finding : Finding
        The finding that the current agent is producing.

    Returns
    -------
    str
        A Dado-Nuevo prefixed version of the finding's title.
    """
    if not previous_findings:
        return my_finding.title

    # Try to find a related previous finding by keyword overlap
    my_keywords = _extract_keywords(my_finding.title)
    best_match: Finding | None = None
    best_score = 0

    for prev in previous_findings:
        if prev.agent == my_finding.agent:
            continue
        prev_keywords = _extract_keywords(prev.title)
        overlap = len(my_keywords & prev_keywords)
        if overlap > best_score:
            best_score = overlap
            best_match = prev

    if best_match is None:
        # Fallback: pick the first finding from a different agent
        for prev in previous_findings:
            if prev.agent != my_finding.agent:
                best_match = prev
                break

    if best_match is not None:
        prefix = (
            f"Agreeing with [{best_match.agent}] on "
            f"\"{best_match.title}\", I add that: {my_finding.title}"
        )
        return prefix

    return my_finding.title


# ──────────────────────────────────────────────
#  Parsing
# ──────────────────────────────────────────────


def parse_finding(text: str) -> Finding | None:
    """Parse a single Inverted Pyramid text block into a Finding.

    Parameters
    ----------
    text : str
        Raw text from the LLM response.

    Returns
    -------
    Finding | None
    """
    lines = text.strip().split("\n")
    title = ""
    detail = ""
    impact = ""
    proposal = ""

    # Try to extract agent name from prefix like "[security]"
    agent_match = re.match(r"^\[(\w+)\]", lines[0]) if lines else None
    agent = agent_match.group(1) if agent_match else "unknown"

    for line in lines:
        line = line.strip()
        if line.startswith("FINDING:"):
            title = line[len("FINDING:"):].strip()
        elif line.startswith("··· Detail:") or line.startswith("···Detail:"):
            detail = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line.startswith("··· Impact:") or line.startswith("···Impact:"):
            impact = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line.startswith("··· Proposal:") or line.startswith("···Proposal:"):
            proposal = line.split(":", 1)[1].strip() if ":" in line else ""

    if not title:
        return None

    # Normalize impact
    impact_lower = impact.lower().strip()
    if "critical" in impact_lower or "critico" in impact_lower or "crítico" in impact_lower:
        impact = "Critical"
    elif "high" in impact_lower or "alto" in impact_lower:
        impact = "High"
    elif "medium" in impact_lower or "medio" in impact_lower:
        impact = "Medium"
    elif "low" in impact_lower or "bajo" in impact_lower:
        impact = "Low"
    else:
        impact = "Medium"

    return Finding(
        agent=agent,
        title=title,
        detail=detail,
        impact=impact,
        proposal=proposal,
        round_num=0,
    )


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful lowercase keywords from text."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "this", "that", "these", "those", "it", "its", "they", "them",
        "their", "we", "us", "our", "you", "your", "he", "him", "his", "she",
        "her", "i", "me", "my", "who", "whom", "which", "what", "not", "no",
        "nor", "and", "but", "or", "for", "so", "yet", "with", "without", "at",
        "in", "on", "by", "from", "to", "into", "through", "during", "before",
        "after", "above", "below", "between", "out", "off", "over", "under",
        "again", "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "only", "own", "same", "so", "than", "too",
        "very",
    }
    words = re.findall(r"\w{4,}", text.lower())
    return {w for w in words if w not in stop_words}
