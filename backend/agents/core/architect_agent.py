"""Architect agent — orchestrates dependency mapping and design-pattern matching.

The ArchitectAgent focuses on system structure: how modules relate, whether
dependencies form cycles, and whether the code uses well-known patterns
cleanly. It delegates to 2 sub-agents and uses 2 tools to ground its analysis.

Sub-agents:
  - DependencyMapper      (map_dependencies) — JSON: modules/circular/suggestions
  - DesignPatternMatcher  (match_patterns)    — list: pattern + confidence
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.agents.subagents.dependency_mapper import DependencyMapper
from backend.agents.subagents.design_pattern_matcher import DesignPatternMatcher
from backend.agents.tools.code_search_tool import CodeSearchTool
from backend.agents.tools.dependency_analysis_tool import DependencyAnalysisTool
from backend.agents.tools.documentation_lookup_tool import DocumentationLookupTool
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """Reviews architecture by coordinating 2 sub-agents + 2 tools."""

    def __init__(self) -> None:
        super().__init__(
            name="architect",
            role_description="software architecture design and system planning",
        )
        self.subagents: dict[str, Any] = {
            "dependency_mapper": DependencyMapper(),
            "design_pattern_matcher": DesignPatternMatcher(),
        }
        self.tools: dict[str, Any] = {
            "code_search": CodeSearchTool(),
            "dependency_analysis": DependencyAnalysisTool(),
            "documentation_lookup": DocumentationLookupTool(),
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
        logger.info("[architect] Round 1: launching 2 sub-agents + 2 tools")

        deps_task = self._safe_call(
            "dependency_mapper",
            self.subagents["dependency_mapper"].map_dependencies(code),
        )
        pattern_task = self._safe_call(
            "design_pattern_matcher",
            self.subagents["design_pattern_matcher"].match_patterns(code),
        )
        # Deterministic tools
        import_search = self.tools["code_search"].execute(
            code=code, pattern="", search_type="import"
        )
        deps_tool = self.tools["dependency_analysis"].execute(
            code=code, analysis_type="all"
        )

        deps, patterns, imports, deps_tool_res = await asyncio.gather(
            deps_task, pattern_task, import_search, deps_tool
        )

        self._round1_cache = {
            "dependencies": deps or {},
            "patterns": patterns or [],
            "imports": imports or {},
            "deps_tool": deps_tool_res or {},
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
            logger.warning("[architect] sub-agent %s failed: %s", name, e)
            return []

    @staticmethod
    def _build_subagent_block(cache: dict[str, Any]) -> str:
        lines: list[str] = ["\n### Sub-agent findings (from the architect's team):\n"]

        deps = cache.get("dependencies") or {}
        patterns = cache.get("patterns") or []
        imports = cache.get("imports") or {}
        deps_tool = cache.get("deps_tool") or {}

        if deps.get("modules"):
            lines.append(f"\n--- dependency_mapper ({len(deps['modules'])} modules) ---")
            for m in deps["modules"][:10]:
                lines.append(
                    f"  - {m.get('name', '?')}: imports={m.get('imports', [])}, "
                    f"dependents={m.get('dependents', [])}"
                )
        if deps.get("circular"):
            lines.append(f"  CIRCULAR DEPENDENCIES: {deps['circular']}")
        if deps.get("suggestions"):
            lines.append(f"  Suggestions: {deps['suggestions'][:3]}")
        if not deps:
            lines.append("\n--- dependency_mapper: no structural data ---")

        if patterns:
            lines.append(f"\n--- design_pattern_matcher ({len(patterns)} patterns) ---")
            for p in patterns[:10]:
                conf = p.get("confidence", "?")
                lines.append(
                    f"  - {p.get('pattern', '?')} (confidence: {conf})"
                    + (f" @ {p.get('location', '?')}" if p.get("location") else "")
                )
                if p.get("reason"):
                    lines.append(f"    Why: {p['reason'][:120]}")
        else:
            lines.append("\n--- design_pattern_matcher: no patterns identified ---")

        if imports.get("count") is not None:
            lines.append(f"\n--- code_search (imports) ---")
            lines.append(f"  Import statements: {imports['count']}")

        if deps_tool:
            lines.append(f"\n--- dependency_analysis (tool) ---")
            for k, v in list(deps_tool.items())[:6]:
                lines.append(f"  {k}: {v}")

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
                "\n\nYour job: synthesize architect team findings into at MOST 3 findings. "
                "Only report architecture, dependency, or design issues — stay in your domain. "
                "Use the EXACT format:\n"
                "FINDING: <one-line conclusion>\n"
                "··· Detail: <1-2 sentences, cycle/pattern reference, line numbers>\n"
                "··· Impact: <Critical|High|Medium|Low>\n"
                "··· Proposal: <2-3 sentence refactor with BEFORE/AFTER>\n\n"
                "If no findings in your domain, respond with NO_FINDINGS."
            ),
        ]
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  Specialised entry points (used by /api/chat and MCP)
    # ──────────────────────────────────────────────

    async def suggest_architecture(self, code: str) -> dict[str, Any]:
        deps = await self._safe_call(
            "dependency_mapper",
            self.subagents["dependency_mapper"].map_dependencies(code),
        )
        patterns = await self._safe_call(
            "design_pattern_matcher",
            self.subagents["design_pattern_matcher"].match_patterns(code),
        )
        return {
            "architecture_suggestions": {
                "dependencies": deps,
                "patterns": patterns,
            },
            "assessment": {
                "module_count": len(deps.get("modules", [])),
                "circular_dependencies": len(deps.get("circular", [])),
                "patterns_found": len(patterns),
            },
        }

    async def plan_refactor(
        self, code: str, findings: list[Finding]
    ) -> dict[str, Any]:
        critical_findings = [f for f in findings if f.impact == "Critical"]
        prompt = (
            f"Create refactoring plan based on architectural findings.\n\n"
            f"Code size: {len(code)} chars\n"
            f"Critical findings: {len(critical_findings)}\n\n"
            f"Findings: {findings[:2]}...\n\n"
            "Output structured plan with priority, effort, risk, testing."
        )
        response = await self._call_llm(prompt)
        return {
            "refactoring_plan": response,
            "critical_finding_count": len(critical_findings),
        }

    async def answer_question(
        self, question: str, context: str | None = None, content_type: str = "general", images: list[dict[str, str]] | None = None
    ) -> str:
        return await super().answer_question(question, context, content_type=content_type, images=images)
