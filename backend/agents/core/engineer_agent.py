"""Engineer agent — orchestrates code writing, refactoring, and optimization.

The EngineerAgent is the "doer" of the team. It analyses how the code could
be improved and produces concrete refactors, fixes, and optimisations. It
delegates to 3 sub-agents and uses 1 tool.

Sub-agents:
  - CodeWriter  (write_fix / generate_implementation) — produces concrete code
  - Refactorer  (suggest_refactoring / apply_refactoring) — refactor strategies
  - Optimizer   (suggest_optimization / apply_optimization) — perf optimisations

The Engineer is special: in round 1 it delegates to the 3 sub-agents to
gather *proposed* fixes/refactors/optimisations, then in round 2 (or in
response to a follow-up question) it can apply one of them via
``implement_fix()`` / ``optimize_code()``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.agents.subagents.code_writer import CodeWriter
from backend.agents.subagents.optimizer import Optimizer
from backend.agents.subagents.refactorer import Refactorer
from backend.agents.tools.code_search_tool import CodeSearchTool
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class EngineerAgent(BaseAgent):
    """Implements fixes and optimisations by coordinating 3 sub-agents + 1 tool."""

    def __init__(self) -> None:
        super().__init__(
            name="engineer",
            role_description="code implementation, fixes, and optimization",
        )
        self.subagents: dict[str, Any] = {
            "code_writer": CodeWriter(),
            "refactorer": Refactorer(),
            "optimizer": Optimizer(),
        }
        self.tools: dict[str, Any] = {
            "code_search": CodeSearchTool(),
        }

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        if not code.strip():
            return []
        if round == 1:
            return await self._analyze_round1(code, context, round)
        return await self._analyze_round_n(code, context, round)

    async def _analyze_round1(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        logger.info("[engineer] Round 1: launching 3 sub-agents + 1 tool")

        # Synthesise a single "abstract finding" so the refactorer/optimizer
        # sub-agents have something to chew on in round 1 (they normally
        # take a finding as input).
        synthetic_finding = {
            "title": "general code review",
            "location": "the code as a whole",
            "severity": "Medium",
            "description": "Identify all opportunities to improve implementation quality.",
        }

        refactor_task = self._safe_call(
            "refactorer",
            self.subagents["refactorer"].suggest_refactoring(code, synthetic_finding),
        )
        optimize_task = self._safe_call(
            "optimizer",
            self.subagents["optimizer"].suggest_optimization(code, synthetic_finding),
        )
        # Code writer is best invoked with a concrete spec; in round 1 it
        # just produces a "would write" overview from the prompt.
        writer_task = self._safe_call(
            "code_writer",
            self.subagents["code_writer"].write_fix(code, synthetic_finding),
        )
        # Deterministic tool
        func_search = self.tools["code_search"].execute(
            code=code, pattern="", search_type="function"
        )

        refactor, optimize, writer, funcs = await asyncio.gather(
            refactor_task, optimize_task, writer_task, func_search
        )

        self._round1_cache = {
            "refactor": refactor or {},
            "optimize": optimize or {},
            "writer": writer or "",
            "funcs": funcs or {},
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
            logger.warning("[engineer] sub-agent %s failed: %s", name, e)
            return None if name == "code_writer" else {}

    @staticmethod
    def _build_subagent_block(cache: dict[str, Any]) -> str:
        lines: list[str] = ["\n### Sub-agent findings (from the engineer's team):\n"]

        refactor = cache.get("refactor") or {}
        optimize = cache.get("optimize") or {}
        writer = cache.get("writer") or ""
        funcs = cache.get("funcs") or {}

        if refactor:
            lines.append(f"\n--- refactorer ---")
            lines.append(f"  Strategy: {refactor.get('strategy', '?')}")
            if refactor.get("description"):
                lines.append(f"  Description: {refactor['description'][:200]}")
            if refactor.get("steps"):
                lines.append(f"  Steps: {refactor['steps'][:3]}")
            if refactor.get("impact"):
                lines.append(f"  Impact: {refactor['impact'][:150]}")

        if optimize:
            lines.append(f"\n--- optimizer ---")
            if optimize.get("issue"):
                lines.append(f"  Issue: {optimize['issue'][:150]}")
            if optimize.get("strategy"):
                lines.append(f"  Strategy: {optimize['strategy'][:150]}")
            if optimize.get("estimated_speedup"):
                lines.append(f"  Estimated speedup: {optimize['estimated_speedup']}")

        if writer:
            lines.append(f"\n--- code_writer (fix preview) ---")
            lines.append(f"  {writer[:200]}")

        if funcs.get("count") is not None:
            lines.append(f"\n--- code_search (functions) ---")
            lines.append(f"  Functions: {funcs['count']}")

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
                "\n\nYour job: integrate the engineer's proposed refactors/optimisations "
                "into Inverted-Pyramid findings. Each finding should be ACTIONABLE.\n"
                "Use the EXACT format:\n"
                "FINDING: <one-line conclusion>\n"
                "··· Detail: <evidence, line numbers, before/after sketch>\n"
                "··· Impact: <Critical|High|Medium|Low>\n"
                "··· Proposal: <concrete code change with BEFORE/AFTER>\n\n"
                "If no findings, respond with NO_FINDINGS."
            ),
        ]
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  Action entry points (used by /api/chat and MCP)
    # ──────────────────────────────────────────────

    async def implement_fix(self, code: str, finding: Finding) -> dict[str, Any]:
        """Generate a concrete fix for a specific finding (delegate to CodeWriter)."""
        finding_dict = {
            "title": finding.title,
            "location": finding.detail,
            "severity": finding.impact,
            "description": finding.detail,
            "proposal": finding.proposal,
        }
        fix_code = await self._safe_call(
            "code_writer",
            self.subagents["code_writer"].write_fix(code, finding_dict),
        )
        return {
            "fix_code": fix_code or "",
            "finding_reference": finding.title,
            "implementation_plan": "Apply fix to identified section",
            "testing_required": True,
        }

    async def optimize_code(
        self, code: str, findings: list[Finding]
    ) -> dict[str, Any]:
        """Produce concrete optimisations (delegate to Optimizer)."""
        synthetic = {
            "title": findings[0].title if findings else "general optimisation",
            "location": findings[0].detail if findings else "the code as a whole",
            "severity": findings[0].impact if findings else "Medium",
            "description": findings[0].detail if findings else "",
        }
        opt = await self._safe_call(
            "optimizer",
            self.subagents["optimizer"].suggest_optimization(code, synthetic),
        )
        return {
            "optimizations": opt or {},
            "critical_finding_count": sum(1 for f in findings if f.impact == "Critical"),
        }

    async def answer_question(
        self, question: str, context: str | None = None, content_type: str = "general", images: list[dict[str, str]] | None = None
    ) -> str:
        return await super().answer_question(question, context, content_type=content_type, images=images)
