"""Report formatter — generates a human-readable comparison report."""

from __future__ import annotations

from typing import Any

from backend.benchmark.metrics import BenchmarkMetrics

SEVERITIES = ["Critical", "High", "Medium", "Low"]


def format_report(
    label: str,
    code_preview: str,
    single_metrics: BenchmarkMetrics,
    multi_metrics: BenchmarkMetrics,
    overlap: dict[str, Any],
) -> str:
    """Generate a formatted comparison report.

    Parameters
    ----------
    label : str
        Sample label.
    code_preview : str
        First 500 chars of reviewed code.
    single_metrics : BenchmarkMetrics
        Single-agent results.
    multi_metrics : BenchmarkMetrics
        Multi-agent results.
    overlap : dict
        Overlap analysis from compute_overlap().

    Returns
    -------
    str
        Formatted report.
    """
    lines: list[str] = []
    _sep(lines)
    _title(lines, f"BENCHMARK RESULT: {label}")
    _sep(lines)

    # Code info
    code_lines = code_preview.count("\n")
    code_chars = len(code_preview)
    lines.append(f"Code: {label} ({code_lines} lines, ~{code_chars} chars)")
    lines.append("")

    # Summary table
    _title(lines, "Comparison Summary")
    _sep(lines)
    _table_header(lines)
    _table_row(
        lines,
        "Total findings",
        str(single_metrics.total_findings),
        str(multi_metrics.total_findings),
        _pct_change(single_metrics.total_findings, multi_metrics.total_findings),
    )
    _table_row(
        lines,
        "Categories covered",
        f"{len(single_metrics.coverage_categories)}/6",
        f"{len(multi_metrics.coverage_categories)}/6",
        _pct_change(
            len(single_metrics.coverage_categories),
            len(multi_metrics.coverage_categories),
        ),
    )
    _table_row(
        lines,
        "Avg severity score (1-4)",
        str(single_metrics.avg_severity_score),
        str(multi_metrics.avg_severity_score),
        _pct_change(
            single_metrics.avg_severity_score,
            multi_metrics.avg_severity_score,
        ),
    )
    _table_row(
        lines,
        "Execution time",
        f"{single_metrics.execution_time_s}s",
        f"{multi_metrics.execution_time_s}s",
        _pct_change(
            single_metrics.execution_time_s,
            multi_metrics.execution_time_s,
            higher_is_better=False,
        ),
    )
    _table_row(
        lines,
        "Est. cost (USD)",
        f"${single_metrics.estimated_cost:.4f}",
        f"${multi_metrics.estimated_cost:.4f}",
        _pct_change(
            single_metrics.estimated_cost,
            multi_metrics.estimated_cost,
            higher_is_better=False,
        ),
    )
    _sep_dashed(lines)

    # Overlap
    _title(lines, "Overlap Analysis")
    lines.append(
        f"Single-agent findings ALSO found by multi-agent: "
        f"{overlap['overlap_count']}/{single_metrics.total_findings} "
        f"({overlap['overlap_pct']}%)"
    )
    lines.append(
        f"Findings UNIQUE to single-agent: "
        f"{overlap['single_unique_count']}"
    )
    lines.append(
        f"Findings UNIQUE to multi-agent: "
        f"{overlap['multi_unique_count']}"
    )
    lines.append("")

    # Severity distribution comparison
    _title(lines, "Severity Distribution")
    _sev_header(lines)
    for sev in SEVERITIES:
        s_count = single_metrics.severity_distribution.get(sev, 0)
        m_count = multi_metrics.severity_distribution.get(sev, 0)
        _sev_row(lines, sev, s_count, m_count)
    lines.append("")

    # Category coverage
    _title(lines, "Category Coverage")
    all_cats = sorted(
        single_metrics.coverage_categories | multi_metrics.coverage_categories
    )
    cat_names = {
        "security": "Security",
        "architecture": "Architecture",
        "quality": "Quality",
        "performance": "Performance",
        "ux": "UX / Accessibility",
        "vision": "Visual / UI",
    }
    for cat in all_cats:
        s_covered = "✅" if cat in single_metrics.coverage_categories else "❌"
        m_covered = "✅" if cat in multi_metrics.coverage_categories else "❌"
        name = cat_names.get(cat, cat)
        lines.append(f"  {name:22s}  Single: {s_covered}  Multi: {m_covered}")
    for cat in ["security", "architecture", "quality", "performance", "ux", "vision"]:
        if cat not in all_cats:
            name = cat_names.get(cat, cat)
            lines.append(f"  {name:22s}  Single: ❌  Multi: ❌")
    lines.append("")

    # Unique findings detail
    if overlap.get("multi_unique"):
        _title(lines, "Multi-Agent Unique Findings (not found by generalist)")
        for i, fd in enumerate(overlap["multi_unique"][:10], 1):
            lines.append(
                f"  {i}. [{fd.get('impact', 'N/A')}] {fd.get('title', '')[:100]}"
            )
        if len(overlap["multi_unique"]) > 10:
            lines.append(f"  ... and {len(overlap['multi_unique']) - 10} more")
        lines.append("")

    if overlap.get("single_unique"):
        _title(lines, "Single-Agent Unique Findings (not found by specialists)")
        for i, fd in enumerate(overlap["single_unique"][:5], 1):
            lines.append(
                f"  {i}. [{fd.get('impact', 'N/A')}] {fd.get('title', '')[:100]}"
            )
        if len(overlap["single_unique"]) > 5:
            lines.append(f"  ... and {len(overlap['single_unique']) - 5} more")
        lines.append("")

    # Conclusion
    _title(lines, "Conclusion")
    improvement_metrics = []
    if multi_metrics.total_findings > single_metrics.total_findings:
        ratio = multi_metrics.total_findings / max(single_metrics.total_findings, 1)
        improvement_metrics.append(
            f"Multi-agent finds {ratio:.1f}x more findings"
        )
    if len(multi_metrics.coverage_categories) > len(single_metrics.coverage_categories):
        improvement_metrics.append(
            f"Multi-agent covers more categories "
            f"({len(multi_metrics.coverage_categories)} vs {len(single_metrics.coverage_categories)})"
        )
    if multi_metrics.avg_severity_score > single_metrics.avg_severity_score:
        improvement_metrics.append(
            f"Multi-agent detects higher-severity issues "
            f"({multi_metrics.avg_severity_score:.1f} vs {single_metrics.avg_severity_score:.1f})"
        )
    if overlap.get("overlap_pct", 0) >= 70:
        improvement_metrics.append(
            f"Multi-agent covers {overlap['overlap_pct']}% of generalist findings, "
            f"plus {overlap['multi_unique_count']} additional findings"
        )
    if improvement_metrics:
        for m in improvement_metrics:
            lines.append(f"  ✅ {m}")
    else:
        lines.append("  ⚠️  No clear improvement detected — investigate further.")
    lines.append("")

    _sep(lines)
    return "\n".join(lines)


# ------------------------------------------------------------------
#  Formatting helpers
# ------------------------------------------------------------------


def _sep(lines: list[str]) -> None:
    lines.append("=" * 74)


def _sep_dashed(lines: list[str]) -> None:
    lines.append("-" * 74)


def _title(lines: list[str], text: str) -> None:
    lines.append(f"  {text}")
    lines.append("")


def _table_header(lines: list[str]) -> None:
    lines.append(
        f"  {'Metric':30s} {'Single-Agent':16s} {'Multi-Agent':16s} {'Change':10s}"
    )
    _sep_dashed(lines)


def _table_row(
    lines: list[str],
    metric: str,
    single: str,
    multi: str,
    change: str,
) -> None:
    lines.append(f"  {metric:30s} {single:16s} {multi:16s} {change:>8s}")


def _sev_header(lines: list[str]) -> None:
    lines.append(
        f"  {'Severity':12s} {'Single-Agent':16s} {'Multi-Agent':16s}"
    )
    _sep_dashed(lines)


def _sev_row(lines: list[str], sev: str, s: int, m: int) -> None:
    bar_s = "█" * min(s, 20)
    bar_m = "█" * min(m, 20)
    lines.append(f"  {sev:12s} {s:3d} {bar_s:22s} {m:3d} {bar_m}")


def _pct_change(
    old: float, new: float, higher_is_better: bool = True
) -> str:
    """Format percentage change between old and new values."""
    if old == 0 and new == 0:
        return "  0.0%"
    if old == 0:
        return "  ∞" if higher_is_better else "  -∞"
    change = ((new - old) / old) * 100
    sign = "+" if change >= 0 else ""
    formatted = f"{sign}{change:.1f}%"
    return formatted
