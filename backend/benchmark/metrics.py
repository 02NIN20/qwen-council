"""Metrics collection and comparison for benchmark runs."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from backend.models.schemas import Finding, Report

# Ground truth findings for vulnerable_app.py (known intentional bugs)
ground_truth = [
    {
        "title": "Hardcoded secret API key",
        "detail": "vulnerable_app.py line 19: API_SECRET = \"sk-live-AbCdEfGhIjKlMnOpQrStUvWxYz\" - exposed in source code (CWE-798)",
        "impact": "Critical",
        "proposal": "Remove hardcoded secret. Use environment variables or secure secret management system."
    },
    {
        "title": "SQL injection in user endpoint",
        "detail": "vulnerable_app.py line 54: query = f\"SELECT * FROM users WHERE id = '{user_id}'\" - user input directly interpolated (CWE-89)",
        "impact": "Critical",
        "proposal": "Use parameterized queries: cursor.execute(\"SELECT * FROM users WHERE id = ?\", (user_id,))"
    },
    {
        "title": "XSS vulnerability in search endpoint",
        "detail": "vulnerable_app.py line 86-93: html = f\"... Search results for: {query}...\" - query reflected without sanitization (CWE-79)",
        "impact": "High",
        "proposal": "Escape HTML special characters: html = f\"... Search results for: {html.escape(query)}...\""
    },
    {
        "title": "Missing CSRF protection",
        "detail": "vulnerable_app.py line 150-151: No CSRF tokens on forms - vulnerable to Cross-Site Request Forgery",
        "impact": "Medium",
        "proposal": "Add CSRF tokens to all state-changing forms using Flask-WTF or similar."
    },
    {
        "title": "N+1 query pattern in search",
        "detail": "vulnerable_app.py line 75-83: Loop over users then executes separate query for each user's orders (performance issue)",
        "impact": "Medium",
        "proposal": "Use JOINs: SELECT users.id, users.name, COUNT(orders.id) as order_count FROM users LEFT JOIN orders ON users.id = orders.user_id GROUP BY users.id"
    },
    {
        "title": "Dead code - unused helper method",
        "detail": "vulnerable_app.py line 135-137: _unused_helper() method defined but never called",
        "impact": "Low",
        "proposal": "Remove unused method or implement it if needed."
    },
    {
        "title": "Global mutable state",
        "detail": "vulnerable_app.py line 22: db_connection = None - global mutable state creates tight coupling and thread safety issues",
        "impact": "Medium",
        "proposal": "Use dependency injection or Flask's g object for request-local storage."
    },
    {
        "title": "High cyclomatic complexity",
        "detail": "vulnerable_app.py line 100-132: _dashboard() method has 8+ branching paths and O(n²) algorithm",
        "impact": "High",
        "proposal": "Extract methods, use lookup tables, avoid nested loops."
    }
]

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


def compute_precision_recall_f1(
    single_findings: list[dict[str, Any]],
    multi_findings: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
) -> dict[str, float]:
    """Compute precision, recall, and F1 score against ground truth.

    Parameters
    ----------
    single_findings : list[dict]
        Findings from single-agent mode.
    multi_findings : list[dict]
        Findings from multi-agent mode.
    ground_truth : list[dict]
        Known ground truth vulnerabilities.

    Returns
    -------
    dict with keys:
        single_precision, single_recall, single_f1: metrics for single-agent
        multi_precision, multi_recall, multi_f1: metrics for multi-agent
    """
    def compute_metrics(findings: list[dict[str, Any]]) -> tuple[int, int, int]:
        """Return (true_positives, predicted_positives, actual_positives) for a finding set."""
        true_positives = 0
        predicted_positives = len(findings)
        actual_positives = len(ground_truth)

        for finding in findings:
            for truth in ground_truth:
                # Check if finding matches ground truth (similar title and detail)
                if (finding.get("title", "") == truth.get("title", "") and
                    finding.get("detail", "") == truth.get("detail", "")):
                    true_positives += 1
                    break

        return true_positives, predicted_positives, actual_positives

    # Single-agent metrics
    tp_single, pred_single, actual_single = compute_metrics(single_findings)
    precision_single = tp_single / pred_single if pred_single > 0 else 0.0
    recall_single = tp_single / actual_single if actual_single > 0 else 0.0
    f1_single = 2 * precision_single * recall_single / (precision_single + recall_single) if (precision_single + recall_single) > 0 else 0.0

    # Multi-agent metrics
    tp_multi, pred_multi, actual_multi = compute_metrics(multi_findings)
    precision_multi = tp_multi / pred_multi if pred_multi > 0 else 0.0
    recall_multi = tp_multi / actual_multi if actual_multi > 0 else 0.0
    f1_multi = 2 * precision_multi * recall_multi / (precision_multi + recall_multi) if (precision_multi + recall_multi) > 0 else 0.0

    return {
        "single_precision": round(precision_single, 4),
        "single_recall": round(recall_single, 4),
        "single_f1": round(f1_single, 4),
        "multi_precision": round(precision_multi, 4),
        "multi_recall": round(recall_multi, 4),
        "multi_f1": round(f1_multi, 4),
        "actual_positives": actual_single,
    }


def count_false_positives_per_100_lines(
    findings: list[dict[str, Any]],
    code: str,
) -> float:
    """Count likely false positives per 100 lines of code.

    A finding is considered a likely false positive if it's generic, lacks concrete
    evidence (no line numbers/code snippets), or is a repetitive finding.

    Parameters
    ----------
    findings : list[dict]
        Findings to evaluate.
    code : str
        Source code being reviewed.

    Returns
    -------
    float: False positives per 100 lines of code.
    """
    false_positives = 0

    for finding in findings:
        detail = finding.get("detail", "")
        title = finding.get("title", "")

        # Check for generic findings without concrete evidence
        is_false_positive = False

        # Generic if no line numbers mentioned
        import re
        has_line_numbers = bool(re.search(r'line\s+\d+', detail, re.IGNORECASE))
        has_code_snippet = bool(re.search(r'`?[^`\s]+`?', detail))

        # Generic if finding is too short or too common
        if len(detail) < 50 or len(title) < 10:
            is_false_positive = True
        # Generic security terms without specifics
        elif any(term in detail.lower() for term in ["security issue", "potential problem", "might be"]):
            is_false_positive = True
        # For now, we'll count findings with generic details as false positives
        # In a real implementation, you'd use more sophisticated heuristics
        elif not has_line_numbers and not has_code_snippet:
            is_false_positive = True

        if is_false_positive:
            false_positives += 1

    code_lines = code.count('\n')
    if code_lines == 0:
        return 0.0

    return round((false_positives / code_lines) * 100, 2)
