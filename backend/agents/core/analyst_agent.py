"""Analyst agent — orchestrates static analysis, pattern detection, and complexity.

The AnalystAgent specialises in understanding the code itself: its structure,
its patterns (both good and bad), and its complexity. It delegates to 3
sub-agents and 2 tools, then synthesises the results into Inverted-Pyramid
findings.

Sub-agents:
  - StaticAnalyzer        (analyse_static)         — static issues per line
  - PatternDetector       (detect_patterns)        — design patterns + anti-patterns
  - ComplexityAnalyzerSub (analyze_complexity)     — cyclomatic + cognitive metrics
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.agents.subagents.complexity_analyzer import ComplexityAnalyzerSub
from backend.agents.subagents.pattern_detector import PatternDetector
from backend.agents.subagents.static_analyzer import StaticAnalyzer
from backend.agents.tools.code_search_tool import CodeSearchTool
from backend.agents.tools.static_analysis_tool import StaticAnalysisTool
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """Performs comprehensive code analysis by coordinating 3 sub-agents + 2 tools."""

    def __init__(self) -> None:
        super().__init__(
            name="analyst",
            role_description="code analysis, pattern detection, and anomaly identification",
        )
        self.subagents: dict[str, Any] = {
            "static_analyzer": StaticAnalyzer(),
            "pattern_detector": PatternDetector(),
            "complexity_analyzer": ComplexityAnalyzerSub(),
        }
        self.tools: dict[str, Any] = {
            "code_search": CodeSearchTool(),
            "static_analysis": StaticAnalysisTool(),
        }

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """Direct analysis — one LLM call, no sub-agent delegation."""
        if not code.strip():
            return []
        prompt = self._build_user_prompt(code, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    async def _analyze_round1(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        logger.info("[analyst] Round 1: launching 3 sub-agents + 2 tools")

        static_task = self._safe_call(
            "static_analyzer",
            self.subagents["static_analyzer"].analyze_static(code),
        )
        pattern_task = self._safe_call(
            "pattern_detector",
            self.subagents["pattern_detector"].detect_patterns(code),
        )
        complexity_task = self._safe_call(
            "complexity_analyzer",
            self.subagents["complexity_analyzer"].analyze_complexity(code),
        )
        # Deterministic: function definitions + static metrics
        func_search_task = self.tools["code_search"].execute(
            code=code, pattern="", search_type="function"
        )
        static_tool_task = self.tools["static_analysis"].execute(
            code=code, analysis_type="complexity"
        )

        static_results, pattern_results, complexity_results, funcs, static_tool = await asyncio.gather(
            static_task, pattern_task, complexity_task, func_search_task, static_tool_task
        )

        self._round1_cache = {
            "static": static_results or [],
            "patterns": pattern_results or [],
            "complexity": complexity_results or {},
            "funcs": funcs or {},
            "static_tool": static_tool or {},
        }

        subagent_block = self._build_subagent_block(self._round1_cache)
        prompt = self._build_synthesis_prompt(code, subagent_block, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    async def _analyze_round_n(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        cache = getattr(self, "_round1_cache", None) or {}
        subagent_block = self._build_subagent_block(cache)
        prompt = self._build_synthesis_prompt(code, subagent_block, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    async def _safe_call(name: str, coro: Any) -> Any:
        try:
            return await coro
        except Exception as e:
            logger.warning("[analyst] sub-agent %s failed: %s", name, e)
            return []

    @staticmethod
    def _build_subagent_block(cache: dict[str, Any]) -> str:
        lines: list[str] = ["\n### Sub-agent findings (from the analyst's team):\n"]

        static = cache.get("static") or []
        patterns = cache.get("patterns") or []
        complexity = cache.get("complexity") or {}
        funcs = cache.get("funcs") or {}
        static_tool = cache.get("static_tool") or {}

        if static:
            lines.append(f"\n--- static_analyzer ({len(static)} issues) ---")
            for s in static[:20]:  # cap to avoid prompt bloat
                lines.append(
                    f"  - [{s.get('severity', '?')}] (line {s.get('line', '?')}) {s.get('issue', s.get('type', '?'))}"
                )
        else:
            lines.append("\n--- static_analyzer: no issues found ---")

        if patterns:
            lines.append(f"\n--- pattern_detector ({len(patterns)} patterns/smells) ---")
            for p in patterns[:20]:
                lines.append(
                    f"  - [{p.get('type', '?')}] {p.get('pattern', '?')}"
                    + (f" @ {p.get('location', '?')}" if p.get("location") else "")
                )
        else:
            lines.append("\n--- pattern_detector: no patterns detected ---")

        if complexity:
            lines.append("\n--- complexity_analyzer ---")
            lines.append(f"  Cyclomatic: {complexity.get('cyclomatic_complexity', '?')}")
            lines.append(f"  Cognitive: {complexity.get('cognitive_complexity', '?')}")
            if complexity.get("hotspots"):
                lines.append(f"  Hotspots: {', '.join(complexity['hotspots'][:5])}")

        if funcs.get("count") is not None:
            lines.append(f"\n--- code_search (function count) ---")
            lines.append(f"  Functions found: {funcs['count']}")

        if static_tool.get("estimated_cyclomatic_complexity") is not None:
            lines.append(f"\n--- static_analysis (tool) ---")
            lines.append(
                f"  Tool cyclomatic estimate: {static_tool['estimated_cyclomatic_complexity']}"
            )

        return "\n".join(lines)

    def _build_synthesis_prompt(
        self,
        code: str,
        subagent_block: str,
        context: list[dict[str, Any]] | None,
        round: int,
    ) -> str:
        parts: list[str] = [
            self._build_round_intro(round),
            self._build_context_block(context, round),
            subagent_block,
            f"\n\n### Code to review:\n\n```\n{code}\n```",
            (
                "\n\nYour job: synthesize analyst team findings into at MOST 3 findings. "
                "Only report patterns, complexity, or static analysis issues — stay in your domain. "
                "Use the EXACT format:\n"
                "FINDING: <one-line conclusion>\n"
                "··· Detail: <1-2 sentences, line numbers, complexity score>\n"
                "··· Impact: <Critical|High|Medium|Low>\n"
                "··· Proposal: <2-3 sentence refactor with BEFORE/AFTER>\n\n"
                "If no findings in your domain, respond with NO_FINDINGS."
            ),
        ]
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  Specialised entry points (used by /api/chat and MCP)
    # ──────────────────────────────────────────────

    async def detect_patterns(self, code: str) -> dict[str, Any]:
        patterns = await self._safe_call(
            "pattern_detector",
            self.subagents["pattern_detector"].detect_patterns(code),
        )
        return {
            "patterns_detected": patterns,
            "analysis_type": "pattern_detection",
            "code_size": len(code),
        }

    async def analyze_complexity(self, code: str) -> dict[str, Any]:
        complexity = await self._safe_call(
            "complexity_analyzer",
            self.subagents["complexity_analyzer"].analyze_complexity(code),
        )
        return {
            "complexity_analysis": complexity,
            "metrics": {
                "cyclomatic": complexity.get("cyclomatic_complexity", 0),
                "cognitive": complexity.get("cognitive_complexity", 0),
                "hotspots": complexity.get("hotspots", []),
            },
        }

    async def answer_question(
        self, question: str, context: str | None = None, content_type: str = "general", images: list[dict[str, str]] | None = None
    ) -> str:
        return await super().answer_question(question, context, content_type=content_type, images=images)
