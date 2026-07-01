"""Benchmark runner — executes single-agent and multi-agent modes on the same code.

Usage:
    python -m backend.benchmark.runner --code "path/to/sample.py" [--output report.md]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from backend.benchmark.generalist_agent import GeneralistAgent
from backend.benchmark.metrics import (
    BenchmarkMetrics,
    collect_metrics,
    compute_overlap,
)
from backend.benchmark.report import format_report
from backend.council.orchestrator import CouncilOrchestrator

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class BenchmarkRunner:
    """Runs both modes on the same code and produces a comparison report."""

    def __init__(self) -> None:
        self.generalist = GeneralistAgent()
        self.council = CouncilOrchestrator()

    async def run_single_agent(
        self, code: str
    ) -> tuple[list[Any], BenchmarkMetrics]:
        """Run single-agent (generalist) mode.

        Returns
        -------
        tuple[list[Finding], BenchmarkMetrics]
        """
        logger.info("═══ RUNNING SINGLE-AGENT MODE ═══")
        start = time.monotonic()
        findings = await self.generalist.analyze(code)
        elapsed = time.monotonic() - start

        # Rough token estimate (4 chars ≈ 1 token)
        input_tokens = len(code) // 4 + 500  # system prompt overhead
        output_tokens = sum(
            len(f.title or "") + len(f.detail or "") + len(f.proposal or "")
            for f in findings
        ) // 4

        metrics = collect_metrics(
            mode="single-agent",
            findings=findings,
            execution_time_s=elapsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        logger.info(
            "Single-agent complete: %d findings in %.1fs",
            len(findings), elapsed,
        )
        return findings, metrics

    async def run_multi_agent(self, code: str) -> tuple[list[Any], BenchmarkMetrics]:
        """Run multi-agent (council) mode.

        Returns
        -------
        tuple[list[Finding], BenchmarkMetrics]
        """
        logger.info("═══ RUNNING MULTI-AGENT MODE ═══")
        start = time.monotonic()
        report, session_id, round_data = await self.council.run_council(
            code=code,
        )
        elapsed = time.monotonic() - start

        # Flatten all findings from all rounds for per-agent comparison
        all_findings: list[Any] = []
        flat_by_round: dict[int, list[Any]] = {}
        for r in (1, 2, 3):
            flat: list[Any] = []
            for agent_findings in round_data.get(f"round_{r}", {}).values():
                for f_data in agent_findings:
                    # Reconstruct Finding from dict if needed
                    from backend.models.schemas import Finding as FindingModel
                    try:
                        f = FindingModel(**f_data)
                        flat.append(f)
                        all_findings.append(f)
                    except Exception:
                        pass
            flat_by_round[r] = flat

        # Also include consolidated findings from the report
        consolidated = report.findings

        # Token estimates
        input_tokens = len(code) // 4 * 6 * 3  # 6 agents × 3 rounds
        output_tokens = sum(
            len(f.title or "") + len(f.detail or "") + len(f.proposal or "")
            for f in all_findings
        ) // 4

        metrics = collect_metrics(
            mode="multi-agent",
            findings=all_findings,
            execution_time_s=elapsed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        logger.info(
            "Multi-agent complete: %d raw findings, %d consolidated in %.1fs",
            len(all_findings), len(consolidated), elapsed,
        )
        return all_findings, metrics, report

    async def run_benchmark(
        self, code: str, label: str = "sample"
    ) -> dict[str, Any]:
        """Run both modes and return a full comparison result.

        Parameters
        ----------
        code : str
            Source code to review.
        label : str
            Human-readable label for this code sample.

        Returns
        -------
        dict with keys: label, single_metrics, multi_metrics, overlap, report
        """
        # Run single-agent
        single_findings, single_metrics = await self.run_single_agent(code)

        # Run multi-agent
        multi_findings, multi_metrics, report = await self.run_multi_agent(code)

        # Compute overlap
        single_dicts = [f.model_dump() for f in single_findings]
        multi_dicts = [f.model_dump() for f in multi_findings]
        overlap = compute_overlap(single_dicts, multi_dicts)

        # Generate formatted report
        report_text = format_report(
            label=label,
            code_preview=code[:500],
            single_metrics=single_metrics,
            multi_metrics=multi_metrics,
            overlap=overlap,
        )

        result = {
            "label": label,
            "single_metrics": single_metrics,
            "multi_metrics": multi_metrics,
            "overlap": overlap,
            "report_text": report_text,
            "council_report": report,
        }

        # Print summary
        print(report_text)

        return result


async def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Benchmark multi-agent vs single-agent code review"
    )
    parser.add_argument("--code", type=str, help="Path to source code file")
    parser.add_argument(
        "--inline", type=str, help="Inline code string to review"
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Save report to file"
    )
    args = parser.parse_args()

    if args.code:
        with open(args.code, "r") as f:
            code = f.read()
        label = args.code.split("/")[-1]
    elif args.inline:
        code = args.inline
        label = "inline"
    else:
        print("Provide --code <file> or --inline <code>")
        return

    runner = BenchmarkRunner()
    result = await runner.run_benchmark(code, label=label)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result["report_text"])
        print(f"\nReport saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
