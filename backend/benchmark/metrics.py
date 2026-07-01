"""Metrics collection and comparison for benchmark runs."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from backend.models.schemas import Finding, Report

# Category keywords for domain classification
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "security": [
        "security", "vulnerability", "injection", "xss", "sql", "cwe",
        "authentication", "authorization", "secret", "encryption", "ssl",
        "tls", "csrf", "owasp", "sanitize", "escape", "privilege",
    ],
    "architecture": [
        "architecture", "coupling", "cohesion", "solid", "pattern",
        "scalability", "modular", "dependency", "interface", "abstraction",
        "separation", "concern", "tightly coupled", "circular",
    ],
    "quality": [
        "quality", "dead code", "complexity", "cyclomatic", "duplicate",
        "lint", "convention", "style", "unused", "test", "coverage",
        "responsibility", "function length", "naming",
    ],
    "performance": [
        "performance", "n+1", "query", "cache", "memory leak", "bottleneck",
        "inefficient", "loop", "recursion", "latency", "throughput",
        "optimization", "slow", "timeout", "pool",
    ],
    "ux": [
        "ux", "accessibility", "aria", "keyboard", "contrast", "screen reader",
        "a11y", "tabindex", "focus", "label", "role", "alt text",
        "colour blind", "font size",
    ],
    "vision": [
        "visual", "ui", "layout", "responsive", "css", "anomaly",
        "alignment", "spacing", "overflow", "z-index", "breakpoint",
        "pixel", "render", "dom", "paint",
    ],
}

# Severity weights for scoring
SEVERITY_WEIGHT = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}

SIMILARITY_THRESHOLD = 0.35


@dataclass
class BenchmarkMetrics:
    """Metrics collected from a single benchmark run (one mode)."""

    mode: str  # "single-agent" | "multi-agent"
    total_findings: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    coverage_categories: set[str] = field(default_factory=set)
    severity_distribution: dict[str, int] = field(default_factory=lambda: {
        "Critical": 0, "High": 0, "Medium": 0, "Low": 0,
    })
    avg_severity_score: float = 0.0
    execution_time_s: float = 0.0
    estimated_cost: float = 0.0
    raw_tokens_input: int = 0
    raw_tokens_output: int = 0


def classify_finding_category(finding: dict[str, Any]) -> str:
    """Classify a finding into one of the 6 categories based on keyword matching.

    Returns the category name, or "uncategorised" if no match.
    """
    text = (
        (finding.get("title", "") + " " +
         finding.get("detail", "") + " " +
         finding.get("proposal", ""))
        .lower()
    )
    scores: dict[str, int] = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "uncategorised"


def collect_metrics(
    mode: str,
    findings: list[Finding],
    execution_time_s: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> BenchmarkMetrics:
    """Collect structured metrics from a list of Findings.

    Parameters
    ----------
    mode : str
        "single-agent" or "multi-agent".
    findings : list[Finding]
        Raw findings from the review.
    execution_time_s : float
        Wall-clock time in seconds.
    input_tokens : int
        Estimated input token count.
    output_tokens : int
        Estimated output token count.

    Returns
    -------
    BenchmarkMetrics
        Structured metrics.
    """
    findings_dicts = [f.model_dump() for f in findings]

    # Severity distribution
    sev_dist: dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        sev = f.impact if f.impact in sev_dist else "Medium"
        sev_dist[sev] = sev_dist.get(sev, 0) + 1

    # Coverage categories
    categories: set[str] = set()
    for fd in findings_dicts:
        cat = classify_finding_category(fd)
        if cat != "uncategorised":
            categories.add(cat)

    # Average severity score
    total_weight = sum(
        SEVERITY_WEIGHT.get(f.impact, 2) for f in findings
    ) if findings else 0
    avg_sev = total_weight / len(findings) if findings else 0.0

    # Cost estimate (Qwen-coder-plus: ~$0.004/1K input, ~$0.012/1K output)
    cost = (input_tokens / 1000) * 0.004 + (output_tokens / 1000) * 0.012

    return BenchmarkMetrics(
        mode=mode,
        total_findings=len(findings),
        findings=findings_dicts,
        coverage_categories=categories,
        severity_distribution=sev_dist,
        avg_severity_score=round(avg_sev, 2),
        execution_time_s=round(execution_time_s, 1),
        estimated_cost=round(cost, 4),
        raw_tokens_input=input_tokens,
        raw_tokens_output=output_tokens,
    )


def compute_overlap(
    single_findings: list[dict[str, Any]],
    multi_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute overlap and uniqueness metrics between two finding sets.

    Parameters
    ----------
    single_findings : list[dict]
        Findings from single-agent mode.
    multi_findings : list[dict]
        Findings from multi-agent mode.

    Returns
    -------
    dict with keys:
        overlap_count: number of single findings also found in multi
        overlap_pct: percentage of single findings covered by multi
        single_unique: findings only in single-agent
        multi_unique: findings only in multi-agent
    """
    overlap_count = 0
    matched_multi: set[int] = set()

    for sf in single_findings:
        for i, mf in enumerate(multi_findings):
            if i in matched_multi:
                continue
            similarity = SequenceMatcher(
                None,
                (sf.get("title", "") + sf.get("detail", "")).lower(),
                (mf.get("title", "") + mf.get("detail", "")).lower(),
            ).ratio()
            if similarity >= SIMILARITY_THRESHOLD:
                overlap_count += 1
                matched_multi.add(i)
                break

    overlap_pct = round(
        (overlap_count / len(single_findings) * 100) if single_findings else 0, 1
    )

    single_unique = [
        sf for i, sf in enumerate(single_findings)
        if not any(
            SequenceMatcher(
                None,
                (sf.get("title", "") + sf.get("detail", "")).lower(),
                (mf.get("title", "") + mf.get("detail", "")).lower(),
            ).ratio() >= SIMILARITY_THRESHOLD
            for mf in multi_findings
        )
    ]

    multi_unique = [
        mf for i, mf in enumerate(multi_findings)
        if i not in matched_multi
    ]

    return {
        "overlap_count": overlap_count,
        "overlap_pct": overlap_pct,
        "single_unique": single_unique,
        "multi_unique": multi_unique,
        "single_unique_count": len(single_unique),
        "multi_unique_count": len(multi_unique),
    }
