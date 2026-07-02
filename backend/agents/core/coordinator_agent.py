"""Coordinator agent — orchestrates the review by planning tasks and routing work.

The Coordinator is the meta-agent: instead of producing code findings
itself, it uses TaskPlanner to decide WHICH core agents to activate and
PriorityRouter to assign priorities to findings that come back. This is
what makes the system a real "Agent Society" — the coordinator is the
judge of who works on what.

Sub-agents:
  - TaskPlanner      (plan_review) — which core agents to run
  - PriorityRouter   (route_tasks) — prioritise findings
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.agents.subagents.priority_router import PriorityRouter
from backend.agents.subagents.task_planner import TaskPlanner
from backend.agents.tools.code_search_tool import CodeSearchTool
from backend.agents.tools.dependency_analysis_tool import DependencyAnalysisTool
from backend.agents.tools.documentation_lookup_tool import DocumentationLookupTool
from backend.agents.tools.static_analysis_tool import StaticAnalysisTool
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """Orchestrates the council by planning and routing, not by analysing code directly."""

    def __init__(self) -> None:
        super().__init__(
            name="coordinator",
            role_description="orchestrating work and delegating tasks",
        )
        self.subagents: dict[str, Any] = {
            "task_planner": TaskPlanner(),
            "priority_router": PriorityRouter(),
        }
        self.tools: dict[str, Any] = {
            "code_search": CodeSearchTool(),
            "static_analysis": StaticAnalysisTool(),
            "dependency_analysis": DependencyAnalysisTool(),
            "documentation_lookup": DocumentationLookupTool(),
        }
        # Cached plan from TaskPlanner (so plan_review() can be called once
        # and reused across rounds).
        self._cached_plan: list[dict[str, Any]] = []

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """The Coordinator doesn't produce findings about the code itself.

        Instead, it produces "meta-findings" about the review process:
        which agents were activated, in what order, and why. In round 1
        it runs TaskPlanner + a deterministic static summary. In later
        rounds it focuses on routing and prioritisation.
        """
        if not code.strip():
            return []
        if round == 1:
            return await self._analyze_round1(code, round)
        return await self._analyze_round_n(code, round)

    async def _analyze_round1(
        self, code: str, round: int
    ) -> list[Finding]:
        logger.info("[coordinator] Round 1: planning + routing + static summary")

        # Run task planner + deterministic static analysis in parallel
        plan_task = self._safe_call(
            "task_planner",
            self.subagents["task_planner"].plan_review(code, mode="full"),
        )
        static_task = self.tools["static_analysis"].execute(
            code=code, analysis_type="length"
        )

        plan, static = await asyncio.gather(plan_task, static_task)

        self._cached_plan = plan or []
        self._round1_cache = {
            "plan": plan or [],
            "static": static or {},
        }

        subagent_block = self._build_subagent_block(self._round1_cache)
        prompt = self._build_synthesis_prompt(code, subagent_block, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    async def _analyze_round_n(
        self, code: str, round: int
    ) -> list[Finding]:
        cache = getattr(self, "_round1_cache", None) or {}
        subagent_block = self._build_subagent_block(cache)
        prompt = self._build_synthesis_prompt(code, subagent_block, round)
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
            logger.warning("[coordinator] sub-agent %s failed: %s", name, e)
            return []

    @staticmethod
    def _build_subagent_block(cache: dict[str, Any]) -> str:
        lines: list[str] = ["\n### Sub-agent findings (from the coordinator's team):\n"]

        plan = cache.get("plan") or []
        static = cache.get("static") or {}

        if plan:
            lines.append(f"\n--- task_planner ({len(plan)} tasks) ---")
            for t in plan[:8]:
                if isinstance(t, dict):
                    lines.append(
                        f"  - [{t.get('priority', '?')}] {t.get('agent', '?')}: {t.get('focus_area', '?')}"
                    )
        else:
            lines.append("\n--- task_planner: no plan produced ---")

        if static:
            lines.append(f"\n--- static_analysis (tool) ---")
            lines.append(f"  Total lines: {static.get('total_lines', '?')}")
            if static.get("long_functions"):
                lines.append(
                    f"  Long functions: {len(static['long_functions'])} (need refactor)"
                )

        return "\n".join(lines)

    def _build_synthesis_prompt(
        self,
        code: str,
        subagent_block: str,
        round: int,
    ) -> str:
        parts: list[str] = [
            self._build_round_intro(round),
            subagent_block,
            f"\n\n### Code to review:\n\n```\n{code}\n```",
            (
                "\n\nYour job: produce at MOST 2 META-FINDINGS about the review process itself. "
                "The Coordinator does not critique the code — it reports on how the "
                "review should be structured and what gaps the plan might miss.\n"
                "Use the EXACT format:\n"
                "FINDING: <one-line conclusion about the review strategy>\n"
                "··· Detail: <1 sentence, evidence from the plan, missing agents, scope>\n"
                "··· Impact: <Critical|High|Medium|Low>\n"
                "··· Proposal: <which extra agent to activate, or scope adjustment>\n\n"
                "If no meta-finding is needed, respond with NO_FINDINGS."
            ),
        ]
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  Coordinator-specific actions
    # ──────────────────────────────────────────────

    async def plan_review(
        self, code: str, mode: str = "full"
    ) -> dict[str, Any]:
        """Plan which agents to activate (delegate to TaskPlanner)."""
        tasks = await self._safe_call(
            "task_planner",
            self.subagents["task_planner"].plan_review(code, mode=mode),
        )
        return {
            "agents_to_activate": [t.get("agent") for t in (tasks or [])],
            "tasks": tasks or [],
            "mode": mode,
        }

    async def route_findings(
        self, findings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Prioritise findings (delegate to PriorityRouter)."""
        return await self._safe_call(
            "priority_router",
            self.subagents["priority_router"].route_tasks(findings),
        ) or []

    async def escalate_finding(
        self, finding: Finding, target_agent: str
    ) -> dict[str, Any]:
        """Forward a critical finding to a specific agent for follow-up."""
        prompt = (
            f"Forward this finding to {target_agent}.\n\n"
            f"Finding: {finding.title}\n"
            f"Impact: {finding.impact}\n"
            f"Proposal: {finding.proposal}"
        )
        response = await self._call_llm(prompt)
        return {
            "original_finding": finding.model_dump(),
            "escalated_to": target_agent,
            "response": response,
            "requires_immediate_attention": finding.impact == "Critical",
        }

    async def synthesize_responses(
        self, responses: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Merge multiple agent outputs into a cohesive result."""
        prompt = (
            "Synthesize these agent responses into a cohesive review.\n\n"
            f"Responses: {len(responses)} items\n\n"
            "Create: 1) unified finding list, 2) consensus scoring, 3) prioritised action items."
        )
        response = await self._call_llm(prompt)
        return {
            "synthesized_output": response,
            "total_findings": len(responses),
        }

    async def answer_question(
        self, question: str, context: str | None = None, content_type: str = "general", images: list[dict[str, str]] | None = None
    ) -> str:
        return await super().answer_question(question, context, content_type=content_type, images=images)
