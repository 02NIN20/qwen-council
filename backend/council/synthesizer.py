"""Synthesis engine — consolidates findings across agents and rounds.

Produces the final Report with consensus analysis and an LLM-generated
narrative report (executive summary, risk overview, detailed review,
remediation roadmap).
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.models.schemas import ConsolidatedFinding, Finding, Report
from backend.utils.evidence_validator import batch_validate

logger = logging.getLogger(__name__)

# Minimum similarity ratio to consider two findings as the same topic
SIMILARITY_THRESHOLD = 0.35


async def synthesize(
    all_findings: dict[int, list[Finding]],
    code_context: str = "",
    session_id: str | None = None,
    token_usage: dict[str, Any] | None = None,
) -> Report:
    """Synthesize findings from all rounds into a final Report.

    Parameters
    ----------
    all_findings : dict[int, list[Finding]]
        Mapping of round number -> list of Finding from all agents.
    code_context : str
        Original code being reviewed (for LLM context).
    session_id : str | None
        Optional session ID to attach to the report.

    Returns
    -------
    Report
        Consolidated report with consensus analysis and LLM narrative.
    """
    logger.info(
        "Synthesizing %d rounds of findings",
        len(all_findings),
    )

    # Collect final-round findings (round 3) as the primary source
    final_findings: list[Finding] = []
    for r in (3, 2, 1):
        if r in all_findings and all_findings[r]:
            final_findings = all_findings[r]
            break

    if not final_findings:
        logger.warning("No findings to synthesize")
        return Report(
            findings=[],
            summary="No issues were detected during the review. The code appears to follow best practices for the analysed criteria.",
            risk_overview="No risks identified.",
            detailed_review="All 6 agents completed their analysis and found no significant issues.",
            remediation_roadmap="No remediation required.",
            rounds=len(all_findings),
            session_id=session_id,
        )

    # Cluster similar findings
    clusters = _cluster_findings(final_findings)
    logger.info("Synthesizer: %d raw findings → %d clusters", len(final_findings), len(clusters))

    # Build consolidated findings with filtering
    consolidated: list[ConsolidatedFinding] = []
    discarded_count = 0
    for cluster in clusters:
        cf = _consolidate_cluster(cluster)
        if cf is None:
            continue

        # ── Filtering step: discard low-quality findings ────────────
        # Rule 1: Must cite a line number (evidence of specificity)
        has_line = bool(__import__('re').search(r'\bline\s+\d+\b', cf.detail, __import__('re').IGNORECASE))

        # Rule 2: Must have at least 2 agents agreeing OR be Critical
        enough_votes = len(cf.votes) >= 2 or cf.impact == "Critical"

        # Rule 3: Low consensus + Low severity → discard (noise)
        low_value = (
            cf.consensus_level in ("Low", "No consensus")
            and cf.impact in ("Medium", "Low")
        )

        # Rule 4: Must have a concrete proposal (not generic)
        has_proposal = len(cf.proposal) > 20

        if not has_line and cf.impact != "Critical":
            discarded_count += 1
            logger.debug("Synthesizer discarded: no line number — %s", cf.title[:60])
            continue
        if low_value:
            discarded_count += 1
            logger.debug("Synthesizer discarded: low value — %s", cf.title[:60])
            continue
        if not has_proposal and cf.impact != "Critical":
            discarded_count += 1
            logger.debug("Synthesizer discarded: no concrete proposal — %s", cf.title[:60])
            continue
        if not enough_votes and cf.impact != "Critical":
            discarded_count += 1
            logger.debug("Synthesizer discarded: insufficient votes — %s", cf.title[:60])
            continue

        consolidated.append(cf)

    logger.info(
        "Synthesizer: %d consolidated, %d discarded (%.0f%% kept)",
        len(consolidated), discarded_count,
        (len(consolidated) / max(len(clusters), 1)) * 100,
    )

    # ── Evidence Validation: verify findings against actual source code ──
    if consolidated and code_context:
        validated, rejected = batch_validate(consolidated, code_context)
        ev_discarded = len(rejected)
        if ev_discarded > 0:
            consolidated = validated
            logger.info(
                "Evidence validator: discarded %d/%d findings (%.0f%% kept after validation)",
                ev_discarded, ev_discarded + len(validated),
                (len(validated) / max(ev_discarded + len(validated), 1)) * 100,
            )

    # Sort by severity: Critical -> High -> Medium -> Low
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    consolidated.sort(
        key=lambda x: severity_order.get(x.impact, 99)
    )

    # Build agent metrics
    agent_metrics = _build_agent_metrics(final_findings, consolidated)

    # Generate LLM-powered narrative report
    narrative = await _generate_narrative(
        consolidated=consolidated,
        agent_metrics=agent_metrics,
        code_context=code_context[:2000],  # truncate to save tokens
    )

    return Report(
        findings=consolidated,
        summary=narrative.get("summary", ""),
        risk_overview=narrative.get("risk_overview", ""),
        detailed_review=narrative.get("detailed_review", ""),
        remediation_roadmap=narrative.get("remediation_roadmap", ""),
        agent_metrics=agent_metrics,
        token_usage=token_usage or {},
        rounds=len(all_findings),
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
#  LLM narrative generation
# ---------------------------------------------------------------------------


async def _generate_narrative(
    consolidated: list[ConsolidatedFinding],
    agent_metrics: dict[str, Any],
    code_context: str,
) -> dict[str, str]:
    """Use the LLM to generate a structured narrative report.

    Returns a dict with keys: summary, risk_overview, detailed_review, remediation_roadmap.
    If the LLM call fails, falls back to template-generated text.
    """
    try:
        client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=300,
        )

        findings_json = json.dumps(
            [f.model_dump() for f in consolidated],
            indent=2,
            ensure_ascii=False,
        )
        metrics_json = json.dumps(agent_metrics, indent=2, ensure_ascii=False)

        system_prompt = (
            "You are a senior technical report writer. Generate a structured code review report "
            "based on the consolidated findings from 6 AI agents (coordinator, analyst, architect, "
            "performance, UX, vision).\n\n"
            "Your response MUST be valid JSON with exactly 4 keys, where each value is a PLAIN TEXT STRING "
            "(not a list, not an object):\n"
            '  "summary": <2-3 paragraph executive summary for engineering leadership, plain text>\n'
            '  "risk_overview": <risk heatmap as plain text: list critical/high risks with business impact>\n'
            '  "detailed_review": <per-finding detailed analysis as plain text with code context>\n'
            '  "remediation_roadmap": <prioritized fix plan as plain text with effort estimates>\n\n'
            "IMPORTANT: Each value must be a string, NOT a list or object.\n\n"
            "Write in English. Be specific. Reference actual finding titles and code patterns. "
            "Do NOT mention that you are an AI. Write as if you are a senior engineer presenting to a team."
        )

        user_prompt = (
            f"### Code reviewed (first 2000 chars):\n```\n{code_context}\n```\n\n"
            f"### Consolidated findings ({len(consolidated)} total):\n{findings_json}\n\n"
            f"### Agent metrics:\n{metrics_json}\n\n"
            "Generate the structured report as JSON with keys: summary, risk_overview, detailed_review, remediation_roadmap."
        )

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""
        result = json.loads(content)
        # Ensure all fields are strings (LLM may return lists/objects)
        return {
            "summary": _ensure_str(result.get("summary", "")),
            "risk_overview": _ensure_str(result.get("risk_overview", "")),
            "detailed_review": _ensure_str(result.get("detailed_review", "")),
            "remediation_roadmap": _ensure_str(result.get("remediation_roadmap", "")),
        }

    except Exception:
        logger.exception("LLM narrative generation failed, using fallback")
        return _fallback_narrative(consolidated)


def _fallback_narrative(
    consolidated: list[ConsolidatedFinding],
) -> dict[str, str]:
    """Generate a template-based narrative when LLM is unavailable."""
    critical = sum(1 for f in consolidated if f.impact == "Critical")
    high = sum(1 for f in consolidated if f.impact == "High")
    medium = sum(1 for f in consolidated if f.impact == "Medium")
    low = sum(1 for f in consolidated if f.impact == "Low")
    high_consensus = sum(1 for f in consolidated if f.consensus_level == "High")

    summary = (
        f"Code review complete: {len(consolidated)} findings identified "
        f"({critical} critical, {high} high, {medium} medium, {low} low). "
        f"{high_consensus} findings have strong consensus across agents. "
        f"See detailed breakdown below."
    )

    risk_lines = []
    for f in consolidated:
        if f.impact in ("Critical", "High"):
            risk_lines.append(f"- **[{f.impact}]** {f.title} (consensus: {f.consensus_score})")
    risk_overview = "\n".join(risk_lines) if risk_lines else "No critical or high risks identified."

    detail_lines = []
    for i, f in enumerate(consolidated, 1):
        votes_str = ", ".join(f"{a}: {s}" for a, s in f.votes.items())
        detail_lines.append(
            f"### {i}. [{f.impact}] {f.title}\n"
            f"**Evidence:** {f.detail}\n"
            f"**Proposal:** {f.proposal}\n"
            f"**Consensus:** {f.consensus_level} ({f.consensus_score}) | **Votes:** {votes_str}\n"
        )
    detailed_review = "\n".join(detail_lines)

    remediation_lines = []
    for i, f in enumerate(consolidated, 1):
        remediation_lines.append(f"{i}. **[{f.impact}]** {f.title} — {f.proposal[:100]}...")
    remediation_roadmap = (
        "### Immediate (Critical):\n" + "\n".join(
            f"- {f.title}: {f.proposal[:120]}"
            for f in consolidated if f.impact == "Critical"
        ) + "\n\n### Short-term (High/Medium):\n" + "\n".join(
            f"- {f.title}: {f.proposal[:120]}"
            for f in consolidated if f.impact in ("High", "Medium")
        ) + "\n\n### Nice-to-have (Low):\n" + "\n".join(
            f"- {f.title}: {f.proposal[:120]}"
            for f in consolidated if f.impact == "Low"
        ) if consolidated else "No remediation required."
    )

    return {
        "summary": summary,
        "risk_overview": risk_overview,
        "detailed_review": detailed_review,
        "remediation_roadmap": remediation_roadmap,
    }


# ---------------------------------------------------------------------------
#  Clustering & consolidation (unchanged logic)
# ---------------------------------------------------------------------------


def _cluster_findings(findings: list[Finding]) -> list[list[Finding]]:
    """Group similar findings into clusters based on text similarity."""
    clusters: list[list[Finding]] = []

    for finding in findings:
        best_cluster_idx = -1
        best_score = 0.0

        for idx, cluster in enumerate(clusters):
            representative = cluster[0]
            score = _text_similarity(
                finding.title, representative.title
            )
            if score > best_score and score >= SIMILARITY_THRESHOLD:
                best_score = score
                best_cluster_idx = idx

        if best_cluster_idx >= 0:
            clusters[best_cluster_idx].append(finding)
        else:
            clusters.append([finding])

    return clusters


def _agent_domain_weight(agent_name: str, finding_title: str) -> float:
    """Return a weight [0.25 .. 2.0] for how relevant an agent's domain is to a finding.

    Agents get full weight (2.0) when the finding matches their specialty,
    reduced weight (0.5-1.0) for overlapping domains, and minimum weight
    (0.25) for unrelated domains.
    """
    title_lower = finding_title.lower()
    DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "critic": ["security", "sql injection", "xss", "csrf", "injection", "vulnerab",
                   "auth", "sensitive", "exposed", "secret", "password", "debug",
                   "eval", "os.system", "subprocess", "command", "deseriali",
                   "traversal", "path traversal", "cwe"],
        "analyst": ["complexity", "pattern", "anti-pattern", "duplication", "dead code",
                    "nesting", "cyclomatic", "code smell", "readability", "maintainab"],
        "architect": ["architecture", "coupling", "cohesion", "dependency", "solid",
                      "interface", "separation", "layer", "module", "design pattern",
                      "god object", "monolith", "scalab"],
        "engineer": ["performance", "optimiz", "refactor", "memory leak", "race condition",
                     "concurrency", "error handling", "exception", "logging", "fix",
                     "implementation", "bug", "crash", "null", "undefined"],
        "researcher": ["documentation", "best practice", "standard", "compliance",
                       "reference", "deprecated", "version", "migration", "guide"],
        "coordinator": ["critical", "escalat", "overview", "summary", "synthesis"],
    }
    agent_keywords = DOMAIN_KEYWORDS.get(agent_name, [])
    if not agent_keywords:
        return 1.0
    matches = sum(1 for kw in agent_keywords if kw in title_lower)
    if matches >= 2:
        return 2.0
    elif matches == 1:
        return 1.5
    elif any(kw[:4] in title_lower or title_lower in kw for kw in agent_keywords):
        return 1.0
    return 0.25


def _consolidate_cluster(
    cluster: list[Finding],
) -> ConsolidatedFinding | None:
    """Merge a cluster of similar findings into one ConsolidatedFinding."""
    if not cluster:
        return None

    # Pick the representative: highest domain-weighted impact from longest title
    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    cluster_sorted = sorted(
        cluster,
        key=lambda f: (
            severity_order.get(f.impact, 99),
            -len(f.title),
        ),
    )
    rep = cluster_sorted[0]

    # Gather votes with expertise weighting
    votes: dict[str, str] = {}
    weighted_severity: dict[str, float] = {"Critical": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.0}
    total_weight = 0.0
    top_severity_weight = 0.0
    for f in cluster:
        votes[f.agent] = f.impact
        weight = _agent_domain_weight(f.agent, f.title)
        sev_score = weighted_severity.get(f.impact, 1.0)
        total_weight += weight
        top_severity_weight += weight * (sev_score / 4.0)

    # Consensus: weighted agreement on severity
    total_agents = 6
    severity_counts = Counter(votes.values())
    most_common_count = severity_counts.most_common(1)[0][1] if severity_counts else 0
    # Apply weighting: effective agreement boosted by domain relevance
    weighted_agreement = (most_common_count / total_agents) * (top_severity_weight / max(total_weight, 0.01))
    agreement_ratio = min(1.0, weighted_agreement)
    consensus_score = agreement_ratio

    if agreement_ratio >= 0.8:
        consensus_level = "High"
    elif agreement_ratio >= 0.5:
        consensus_level = "Medium"
    elif agreement_ratio >= 0.3:
        consensus_level = "Low"
    else:
        consensus_level = "No consensus"

    # Merge details (unique, non-empty)
    all_details = list({f.detail for f in cluster if f.detail})
    merged_detail = " | ".join(all_details) if all_details else rep.detail

    # Pick the strongest proposal (from highest-impact finding)
    proposal = rep.proposal

    return ConsolidatedFinding(
        title=rep.title,
        detail=merged_detail,
        impact=rep.impact,
        proposal=proposal,
        votes=votes,
        consensus_level=consensus_level,
        consensus_score=round(consensus_score, 2),
    )


def _build_agent_metrics(
    all_findings: list[Finding],
    consolidated: list[ConsolidatedFinding],
) -> dict[str, Any]:
    """Build per-agent statistics."""
    agent_counts: dict[str, int] = Counter()
    agent_severities: dict[str, list[str]] = {}
    for f in all_findings:
        agent_counts[f.agent] += 1
        if f.agent not in agent_severities:
            agent_severities[f.agent] = []
        agent_severities[f.agent].append(f.impact)

    severity_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    metrics = {}
    for agent in sorted(agent_counts.keys()):
        sevs = agent_severities.get(agent, [])
        top_sev = min(sevs, key=lambda s: severity_rank.get(s, 99)) if sevs else "N/A"
        metrics[agent] = {
            "findings_count": agent_counts[agent],
            "top_severity": top_sev,
            "severity_distribution": dict(Counter(sevs)),
        }

    return {
        "per_agent": metrics,
        "total_raw_findings": len(all_findings),
        "consolidated_findings": len(consolidated),
        "agents_participated": len(agent_counts),
    }


def _ensure_str(value: Any) -> str:
    """Convert a value to string if it isn't already (handles lists/objects from LLM)."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
            for item in value
        )
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _text_similarity(a: str, b: str) -> float:
    """Compute string similarity ratio (0.0 - 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()
