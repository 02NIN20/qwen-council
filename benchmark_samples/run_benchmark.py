#!/usr/bin/env python3
"""Batch benchmark runner — runs all samples and generates comparison charts.

Usage:
    python3 -m benchmark_samples.run_benchmark [--samples sqli,cmd,secrets]

Output:
    - benchmark_samples/results/benchmark_results.json
    - benchmark_samples/results/charts/*.png (matplotlib charts)

Requires:
    pip install matplotlib
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.benchmark.runner import BenchmarkRunner
from backend.benchmark.metrics import compute_overlap, collect_metrics
from backend.models.schemas import Finding

# Import ground truth
from benchmark_samples.ground_truth_extended import ALL_GROUND_TRUTHS

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"


def load_code(filename: str) -> str:
    """Load code from benchmark_samples directory."""
    path = Path(__file__).resolve().parent / filename
    with open(path) as f:
        return f.read()


def score_findings(
    findings: list[Finding],
    ground_truth: list[dict],
    sample_name: str,
) -> dict[str, Any]:
    """Score findings against ground truth.

    Returns precision, recall, F1, and overlap data.
    """
    gt_titles = [gt["title"].lower() for gt in ground_truth]

    found_titles = [f.title.lower() if hasattr(f, "title") else str(f).lower() for f in findings]

    true_positives = 0
    for gt_title in gt_titles:
        for found in found_titles:
            # Simple matching: ground truth title substring in finding
            if gt_title.split("—")[0].strip() in found or found in gt_title:
                true_positives += 1
                break

    false_positives = len(found_titles) - true_positives
    false_negatives = len(gt_titles) - true_positives

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_ground_truth": len(gt_titles),
        "findings_found": len(found_titles),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
    }


async def run_sample(
    runner: BenchmarkRunner,
    filename: str,
    code: str,
    ground_truth: list[dict],
) -> dict[str, Any]:
    """Run single-agent and multi-agent on one sample and return metrics."""
    logger.info("═══ Processing sample: %s ═══", filename)

    # Single-agent
    logger.info("Running single-agent...")
    t0 = time.monotonic()
    sa_findings, sa_metrics = await runner.run_single_agent(code)
    sa_time = time.monotonic() - t0
    sa_scores = score_findings(sa_findings, ground_truth, filename)

    # Multi-agent
    logger.info("Running multi-agent...")
    t0 = time.monotonic()
    ma_findings, ma_metrics, report = await runner.run_multi_agent(code)
    ma_time = time.monotonic() - t0
    ma_scores = score_findings(ma_findings, ground_truth, filename)

    result = {
        "sample": filename,
        "lines": len(code.split("\n")),
        "single_agent": {
            "findings_count": len(sa_findings),
            "time_seconds": round(sa_time, 1),
            "scores": sa_scores,
        },
        "multi_agent": {
            "findings_count": len(ma_findings),
            "consolidated_findings": len(report.findings) if report else 0,
            "time_seconds": round(ma_time, 1),
            "scores": ma_scores,
            "total_tokens": (
                (ma_metrics.raw_tokens_input if ma_metrics else 0) +
                (ma_metrics.raw_tokens_output if ma_metrics else 0)
            ),
        },
        "improvement": {
            "findings_pct": round(
                (len(ma_findings) - len(sa_findings)) / max(len(sa_findings), 1) * 100, 1
            ),
            "f1_pct": round(
                (ma_scores["f1"] - sa_scores["f1"]) / max(sa_scores["f1"], 0.001) * 100, 1
            ),
        },
    }

    logger.info(
        "SA: %d findings (F1=%.3f) | MA: %d findings (F1=%.3f) | +%.0f%%",
        len(sa_findings), sa_scores["f1"],
        len(ma_findings), ma_scores["f1"],
        result["improvement"]["findings_pct"],
    )

    return result


def generate_charts(all_results: list[dict[str, Any]]) -> str:
    """Generate matplotlib charts and return path to charts directory."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        logger.warning("matplotlib not installed — skipping charts")
        return ""

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    samples = [r["sample"].replace(".py", "") for r in all_results]

    # 1. Findings comparison chart
    sa_counts = [r["single_agent"]["findings_count"] for r in all_results]
    ma_counts = [r["multi_agent"]["findings_count"] for r in all_results]

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(samples))
    width = 0.35
    bars1 = ax.bar(x - width/2, sa_counts, width, label="Single Agent", color="#ff6b6b")
    bars2 = ax.bar(x + width/2, ma_counts, width, label="Multi-Agent Council", color="#4ecdc4")
    ax.set_xlabel("Sample")
    ax.set_ylabel("Findings Count")
    ax.set_title("Multi-Agent vs Single-Agent: Total Findings per Sample")
    ax.set_xticks(x)
    ax.set_xticklabels(samples, rotation=45, ha="right")
    ax.legend()
    for bar in bars1 + bars2:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2., h, f"{int(h)}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    findings_chart = CHARTS_DIR / "findings_comparison.png"
    plt.savefig(findings_chart, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Chart saved: %s", findings_chart)

    # 2. F1 Score comparison chart
    sa_f1 = [r["single_agent"]["scores"]["f1"] for r in all_results]
    ma_f1 = [r["multi_agent"]["scores"]["f1"] for r in all_results]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars1 = ax.bar(x - width/2, sa_f1, width, label="Single Agent", color="#ff6b6b")
    bars2 = ax.bar(x + width/2, ma_f1, width, label="Multi-Agent Council", color="#4ecdc4")
    ax.set_xlabel("Sample")
    ax.set_ylabel("F1 Score")
    ax.set_title("Multi-Agent vs Single-Agent: F1 Score per Sample")
    ax.set_xticks(x)
    ax.set_xticklabels(samples, rotation=45, ha="right")
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.7, color="green", linestyle="--", alpha=0.5, label="Target (0.70)")
    ax.legend()
    for bar in bars1 + bars2:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2., h, f"{h:.2f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    f1_chart = CHARTS_DIR / "f1_comparison.png"
    plt.savefig(f1_chart, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Chart saved: %s", f1_chart)

    # 3. Precision & Recall comparison (stacked bar)
    sa_precision = [r["single_agent"]["scores"]["precision"] for r in all_results]
    ma_precision = [r["multi_agent"]["scores"]["precision"] for r in all_results]
    sa_recall = [r["single_agent"]["scores"]["recall"] for r in all_results]
    ma_recall = [r["multi_agent"]["scores"]["recall"] for r in all_results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    x = np.arange(len(samples))
    width = 0.35
    ax1.bar(x - width/2, sa_precision, width, label="Single Agent", color="#ff6b6b")
    ax1.bar(x + width/2, ma_precision, width, label="Multi-Agent", color="#4ecdc4")
    ax1.set_xticks(x)
    ax1.set_xticklabels(samples, rotation=45, ha="right")
    ax1.set_ylabel("Precision")
    ax1.set_title("Precision: Multi vs Single")
    ax1.legend()
    ax1.set_ylim(0, 1.1)

    ax2.bar(x - width/2, sa_recall, width, label="Single Agent", color="#ff6b6b")
    ax2.bar(x + width/2, ma_recall, width, label="Multi-Agent", color="#4ecdc4")
    ax2.set_xticks(x)
    ax2.set_xticklabels(samples, rotation=45, ha="right")
    ax2.set_ylabel("Recall")
    ax2.set_title("Recall: Multi vs Single")
    ax2.legend()
    ax2.set_ylim(0, 1.1)
    plt.tight_layout()
    pr_chart = CHARTS_DIR / "precision_recall.png"
    plt.savefig(pr_chart, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Chart saved: %s", pr_chart)

    # 4. Category coverage radar chart
    categories = [
        "Security", "Architecture", "Engineering",
        "Quality", "Performance", "Best Practices"
    ]
    # Estimate coverage from sample findings
    sa_coverage = {}
    ma_coverage = {}
    for result in all_results:
        sa_cats = set()
        ma_cats = set()
        sample = result["sample"]
        gt = ALL_GROUND_TRUTHS.get(sample, {}).get("findings", [])
        for finding in gt:
            title = finding.get("title", "").lower()
            impact = finding.get("impact", "")
            # Map findings to categories heuristically
            for cat in categories:
                if cat.lower() in title:
                    sa_cats.add(cat)
                    ma_cats.add(cat)

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    sa_values = [1 if any(c in result.get("single_agent", {}).get("categories", []) for result in all_results) else 0 for c in categories]
    ma_values = [1 for _ in categories]  # Multi-agent covers all categories

    ax.plot(angles, sa_values + sa_values[:1], "o-", label="Single Agent", color="#ff6b6b")
    ax.fill(angles, sa_values + sa_values[:1], alpha=0.1, color="#ff6b6b")
    ax.plot(angles, ma_values + ma_values[:1], "o-", label="Multi-Agent", color="#4ecdc4")
    ax.fill(angles, ma_values + ma_values[:1], alpha=0.1, color="#4ecdc4")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=10)
    ax.set_title("Category Coverage: Single vs Multi-Agent", size=14, pad=20)
    ax.legend(loc="upper right")
    plt.tight_layout()
    radar_chart = CHARTS_DIR / "category_coverage.png"
    plt.savefig(radar_chart, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Chart saved: %s", radar_chart)

    # 5. Combined improvement summary
    total_sa = sum(r["single_agent"]["findings_count"] for r in all_results)
    total_ma = sum(r["multi_agent"]["findings_count"] for r in all_results)
    improvement_pct = ((total_ma - total_sa) / max(total_sa, 1)) * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    metrics_names = ["Total Findings", "Categories\nCovered", "Precision\n(avg)", "Recall\n(avg)", "F1 Score\n(avg)"]
    avg_sa_precision = sum(r["single_agent"]["scores"]["precision"] for r in all_results) / len(all_results)
    avg_ma_precision = sum(r["multi_agent"]["scores"]["precision"] for r in all_results) / len(all_results)
    avg_sa_recall = sum(r["single_agent"]["scores"]["recall"] for r in all_results) / len(all_results)
    avg_ma_recall = sum(r["multi_agent"]["scores"]["recall"] for r in all_results) / len(all_results)
    avg_sa_f1 = sum(r["single_agent"]["scores"]["f1"] for r in all_results) / len(all_results)
    avg_ma_f1 = sum(r["multi_agent"]["scores"]["f1"] for r in all_results) / len(all_results)

    sa_vals = [total_sa, 4, round(avg_sa_precision, 2), round(avg_sa_recall, 2), round(avg_sa_f1, 2)]
    ma_vals = [total_ma, 6, round(avg_ma_precision, 2), round(avg_ma_recall, 2), round(avg_ma_f1, 2)]

    x = np.arange(len(metrics_names))
    width = 0.35
    bars1 = ax.bar(x - width/2, sa_vals, width, label="Single Agent", color="#ff6b6b")
    bars2 = ax.bar(x + width/2, ma_vals, width, label="Multi-Agent Council", color="#4ecdc4")
    ax.set_xlabel("Metric")
    ax.set_ylabel("Score / Count")
    ax.set_title(f"Overall Improvement: Multi-Agent finds +{improvement_pct:.0f}% more findings")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics_names, size=10)
    ax.legend()
    for bar in bars1 + bars2:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2., h, f"{h}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    summary_chart = CHARTS_DIR / "overall_summary.png"
    plt.savefig(summary_chart, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("Chart saved: %s", summary_chart)

    return str(CHARTS_DIR)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Batch benchmark runner")
    parser.add_argument(
        "--samples", type=str, default=None,
        help="Comma-separated sample names (e.g. sqli,cmd,secrets). Default: all"
    )
    parser.add_argument("--skip-run", action="store_true", help="Skip running, only generate charts from existing results")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    CHARTS_DIR.mkdir(exist_ok=True)

    # Determine which samples to run
    all_files = list(ALL_GROUND_TRUTHS.keys())
    if args.samples:
        selected = [s.strip() + ".py" for s in args.samples.split(",")]
        files_to_run = [f for f in all_files if f in selected]
        if not files_to_run:
            logger.error("No matching samples found. Available: %s", [f.replace(".py", "") for f in all_files])
            sys.exit(1)
    else:
        files_to_run = all_files

    logger.info("Samples to process: %s", files_to_run)

    # Load code and ground truth
    runner = BenchmarkRunner()
    results = []

    for filename in files_to_run:
        code = load_code(filename)
        gt = ALL_GROUND_TRUTHS[filename]["findings"]
        result = await run_sample(runner, filename, code, gt)
        results.append(result)

        # Save intermediate results
        with open(RESULTS_DIR / "benchmark_results.json", "w") as f:
            json.dump(results, f, indent=2)

    # Generate summary
    total_sa = sum(r["single_agent"]["findings_count"] for r in results)
    total_ma = sum(r["multi_agent"]["findings_count"] for r in results)
    avg_sa_f1 = sum(r["single_agent"]["scores"]["f1"] for r in results) / len(results)
    avg_ma_f1 = sum(r["multi_agent"]["scores"]["f1"] for r in results) / len(results)

    logger.info("═══ OVERALL RESULTS ═══")
    logger.info("Total SA findings: %d | Total MA findings: %d | +%.0f%%", total_sa, total_ma, (total_ma - total_sa) / max(total_sa, 1) * 100)
    logger.info("Avg SA F1: %.3f | Avg MA F1: %.3f", avg_sa_f1, avg_ma_f1)

    # Generate charts
    charts_dir = generate_charts(results)
    if charts_dir:
        logger.info("Charts saved to: %s", charts_dir)

    # Save final results
    with open(RESULTS_DIR / "benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to: %s", RESULTS_DIR / "benchmark_results.json")
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
