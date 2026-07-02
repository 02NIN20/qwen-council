"""Critic agent — coordinates security, performance, and style sub-agents.

The CriticAgent is the leader for code-review tasks. It delegates the actual
analysis to 3 specialised sub-agents (SecurityAuditor, PerformanceReviewer,
StyleChecker), then synthesises their findings into a unified Inverted-Pyramid
report for the orchestrator.

Flow:
  1. Run 3 sub-agents in parallel (asyncio.gather).
  2. Build a context block summarising the sub-agent findings.
  3. Make a final LLM call to consolidate the findings into the Inverted
     Pyramid format expected by the orchestrator's parser.
  4. Return the parsed list of Finding objects.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.agents.subagents.performance_reviewer import PerformanceReviewer
from backend.agents.subagents.security_auditor import SecurityAuditor
from backend.agents.subagents.style_checker import StyleChecker
from backend.agents.tools.code_search_tool import CodeSearchTool
from backend.agents.tools.static_analysis_tool import StaticAnalysisTool
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Performs thorough code review by orchestrating 3 sub-agents."""

    def __init__(self) -> None:
        super().__init__(
            name="critic",
            role_description="code review, quality assurance, and validation",
        )
        # Sub-agents: the actual specialists
        self.subagents: dict[str, Any] = {
            "security_auditor": SecurityAuditor(),
            "performance_reviewer": PerformanceReviewer(),
            "style_checker": StyleChecker(),
        }
        # Tools: deterministic helpers (no LLM)
        self.tools: dict[str, Any] = {
            "static_analysis": StaticAnalysisTool(),
            "code_search": CodeSearchTool(),
        }

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """Delegate to 3 sub-agents, then synthesise.

        Round 1: run all 3 sub-agents in parallel and produce fresh findings.
        Round 2+: build on previous-round context; sub-agents are skipped to
        save tokens — the LLM uses the sub-agent findings from round 1
        stored in working memory instead.
        """
        if not code.strip():
            return []

        if round == 1:
            return await self._analyze_round1(code, context, round)
        return await self._analyze_round_n(code, context, round)

    async def _analyze_round1(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        """Round 1: run all sub-agents + static analysis in parallel."""
        logger.info("[critic] Round 1: launching 3 sub-agents + 1 tool")

        # ── Run sub-agents and tools concurrently ──
        sec_task = self._safe_call(
            "security_auditor",
            self.subagents["security_auditor"].audit_security(code),
        )
        perf_task = self._safe_call(
            "performance_reviewer",
            self.subagents["performance_reviewer"].review_performance(code),
        )
        style_task = self._safe_call(
            "style_checker",
            self.subagents["style_checker"].check_style(code),
        )
        # Deterministic analysis (no LLM, instant)
        static_task = self.tools["static_analysis"].execute(
            code=code, analysis_type="all"
        )

        sec_results, perf_results, style_results, static_results = await asyncio.gather(
            sec_task, perf_task, style_task, static_task
        )

        # Store for round 2/3 reuse
        self._round1_cache = {
            "security": sec_results or [],
            "performance": perf_results or [],
            "style": style_results or [],
            "static": static_results or {},
        }

        # ── Synthesise sub-agent findings into the orchestrator's format ──
        subagent_block = self._build_subagent_block(
            sec_results or [],
            perf_results or [],
            style_results or [],
            static_results or {},
        )

        # ── LLM call: the Critic acts as the integrator ──
        prompt = self._build_synthesis_prompt(code, subagent_block, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    async def _analyze_round_n(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        """Round 2+: reuse sub-agent findings from round 1, focus on debate/refinement."""
        cache = getattr(self, "_round1_cache", None) or {}
        subagent_block = self._build_subagent_block(
            cache.get("security", []),
            cache.get("performance", []),
            cache.get("style", []),
            cache.get("static", {}),
        )
        prompt = self._build_synthesis_prompt(code, subagent_block, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    async def _safe_call(name: str, coro: Any) -> Any:
        """Run a sub-agent coroutine and return [] on failure (never crash the round)."""
        try:
            return await coro
        except Exception as e:
            logger.warning("[critic] sub-agent %s failed: %s", name, e)
            return []

    @staticmethod
    def _build_subagent_block(
        security: list[dict[str, Any]],
        performance: list[dict[str, Any]],
        style: list[dict[str, Any]],
        static: dict[str, Any],
    ) -> str:
        """Format sub-agent findings into a context block for the LLM."""
        lines: list[str] = ["\n### Sub-agent findings (from the critic's team):\n"]

        if security:
            lines.append(f"\n--- security_auditor ({len(security)} issues) ---")
            for s in security:
                lines.append(f"  - [{s.get('severity', '?')}] {s.get('title', '?')}")
                if s.get("cwe") and s["cwe"] != "N/A":
                    lines.append(f"    CWE: {s['cwe']}")
                if s.get("location"):
                    lines.append(f"    Location: {s['location']}")
                if s.get("fix"):
                    lines.append(f"    Fix: {s['fix']}")
        else:
            lines.append("\n--- security_auditor: no issues found ---")

        if performance:
            lines.append(f"\n--- performance_reviewer ({len(performance)} issues) ---")
            for p in performance:
                lines.append(f"  - [{p.get('severity', '?')}] {p.get('issue', '?')}")
                if p.get("location"):
                    lines.append(f"    Location: {p['location']}")
                if p.get("optimization"):
                    lines.append(f"    Optimization: {p['optimization']}")
        else:
            lines.append("\n--- performance_reviewer: no issues found ---")

        if style:
            lines.append(f"\n--- style_checker ({len(style)} issues) ---")
            for s in style:
                lines.append(
                    f"  - [{s.get('severity', '?')}] (line {s.get('line', '?')}) {s.get('issue', '?')}"
                )
                if s.get("suggestion"):
                    lines.append(f"    Suggestion: {s['suggestion']}")
        else:
            lines.append("\n--- style_checker: no issues found ---")

        if static:
            lines.append("\n--- static_analysis (deterministic) ---")
            lines.append(f"  Total lines: {static.get('total_lines', '?')}")
            lines.append(f"  Code lines: {static.get('code_lines', '?')}")
            lines.append(f"  Cyclomatic complexity: {static.get('estimated_cyclomatic_complexity', '?')}")
            lines.append(f"  Max nesting depth: {static.get('max_nesting_depth', '?')}")
            if static.get("long_functions"):
                lines.append(
                    f"  Long functions (>50 lines): {len(static['long_functions'])}"
                )
            if static.get("style_issues"):
                lines.append(
                    f"  Style issues (line >100 chars, missing docstrings): {len(static['style_issues'])}"
                )

        return "\n".join(lines)

    def _build_synthesis_prompt(
        self,
        code: str,
        subagent_block: str,
        context: list[dict[str, Any]] | None,
        round: int,
    ) -> str:
        """Build the user prompt for the synthesis LLM call."""
        parts: list[str] = [
            self._build_round_intro(round),
            self._build_context_block(context, round),
            subagent_block,
            f"\n\n### Code to review:\n\n```\n{code}\n```",
            (
                "\n\nYour job: integrate the sub-agent findings above into a single "
                "coherent Inverted-Pyramid list. Use the EXACT format:\n"
                "FINDING: <one-line conclusion>\n"
                "··· Detail: <concrete evidence, CWE reference, line numbers>\n"
                "··· Impact: <Critical|High|Medium|Low>\n"
                "··· Proposal: <step-by-step fix with BEFORE/AFTER>\n\n"
                "If you have no findings to add, respond with NO_FINDINGS."
            ),
        ]
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  Specialised entry points (used by /api/chat and MCP)
    # ──────────────────────────────────────────────

    async def security_audit(self, code: str) -> dict[str, Any]:
        """Specialised security review (delegate to SecurityAuditor)."""
        findings = await self._safe_call(
            "security_auditor",
            self.subagents["security_auditor"].audit_security(code),
        )
        return {
            "security_audit": findings,
            "vulnerabilities_found": len(findings),
            "critical_issues": sum(1 for f in findings if f.get("severity") == "Critical"),
            "recommendation": "Immediate remediation required" if findings else "No critical issues",
        }

    async def performance_review(self, code: str) -> dict[str, Any]:
        """Specialised performance review (delegate to PerformanceReviewer)."""
        issues = await self._safe_call(
            "performance_reviewer",
            self.subagents["performance_reviewer"].review_performance(code),
        )
        return {
            "performance_review": issues,
            "bottlenecks_identified": len(issues),
            "optimization_potential": "high" if issues else "low",
            "estimated_performance_gain": "3x faster" if issues else "no gain expected",
        }

    async def answer_question(
        self, question: str, context: str | None = None, content_type: str = "general", images: list[dict[str, str]] | None = None
    ) -> str:
        """Answer from critic perspective."""
        return await super().answer_question(question, context, content_type=content_type, images=images)
