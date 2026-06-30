"""Council orchestrator — runs the 3-round debate and produces the final report.

Flow:
  1. Round 1: All 5 agents analyse the code independently (parallel).
  2. Round 2: Each agent receives the findings from Round 1 and debates (parallel).
  3. Round 3: Each agent receives the debates from Round 2 and refines (parallel).
  4. Synthesis: Consolidates findings, counts votes, determines consensus.
  5. Memory: Save episodic memory, check for semantic consolidation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.performance_agent import PerformanceAgent
from backend.agents.quality_agent import QualityAgent
from backend.agents.security_agent import SecurityAgent
from backend.agents.ux_agent import UXAgent
from backend.agents.vision_agent import VisionAgent
from backend.config import settings
from backend.council.synthesizer import synthesize
from backend.memory.consolidator import Consolidator
from backend.memory.episodic_memory import EpisodicMemoryManager
from backend.memory.semantic_memory import SemanticMemoryManager
from backend.memory.working_memory import WorkingMemory
from backend.models.db import async_session_factory
from backend.models.schemas import Finding, Report

logger = logging.getLogger(__name__)


class CouncilOrchestrator:
    """Manages the full council debate lifecycle."""

    def __init__(self) -> None:
        self.agents = {
            "security": SecurityAgent(),
            "architecture": ArchitectureAgent(),
            "quality": QualityAgent(),
            "performance": PerformanceAgent(),
            "ux": UXAgent(),
            "vision": VisionAgent(),
        }
        self.working_memory = WorkingMemory()

    async def run_council(
        self,
        code: str,
        session_id: str | None = None,
        image_url: str | None = None,
    ) -> tuple[Report, str, dict[str, Any]]:
        """Execute the full 3-round council debate.

        Parameters
        ----------
        code : str
            Source code to review.
        session_id : str | None
            Existing session ID for memory continuity.
        image_url : str | None
            Optional image URL for visual analysis (vision agent).

        Returns
        -------
        tuple[Report, str, dict[str, Any]]
            (final_report, session_id, round_data)
        """
        if not session_id:
            session_id = f"ses-{uuid.uuid4().hex[:12]}"

        # Store in working memory
        self.working_memory.set(session_id, {"code": code, "status": "in_progress"})

        # Retrieve relevant semantic memory patterns
        semantic_patterns = await self._retrieve_semantic_context(code)

        all_findings: dict[int, list[Finding]] = {}
        round_data: dict[str, Any] = {}

        # ── Round 1: Individual analysis ──────────────────────
        logger.info("[%s] Starting Round 1: Individual analysis", session_id)
        round1_findings = await self._run_round(
            code=code,
            round_num=1,
            context_findings=None,
            semantic_context=semantic_patterns,
            image_url=image_url,
        )
        all_findings[1] = round1_findings
        round_data["round_1"] = {
            agent: [f.model_dump() for f in findings]
            for agent, findings in round1_findings.items()
        }
        self.working_memory.set(session_id, {"round1_findings": round1_findings})
        logger.info(
            "[%s] Round 1 complete: %d total findings",
            session_id,
            sum(len(v) for v in round1_findings.values()),
        )

        # ── Round 2: Cross-debate (Given-New) ────────────────
        logger.info("[%s] Starting Round 2: Cross-debate", session_id)
        round2_findings = await self._run_round(
            code=code,
            round_num=2,
            context_findings=round1_findings,
            semantic_context=semantic_patterns,
            image_url=image_url,
        )
        all_findings[2] = round2_findings
        round_data["round_2"] = {
            agent: [f.model_dump() for f in findings]
            for agent, findings in round2_findings.items()
        }
        self.working_memory.set(session_id, {"round2_findings": round2_findings})
        logger.info(
            "[%s] Round 2 complete: %d total findings",
            session_id,
            sum(len(v) for v in round2_findings.values()),
        )

        # ── Round 3: Refinement ──────────────────────────────
        logger.info("[%s] Starting Round 3: Refinement", session_id)
        round3_findings = await self._run_round(
            code=code,
            round_num=3,
            context_findings=round2_findings,
            semantic_context=semantic_patterns,
            image_url=image_url,
        )
        all_findings[3] = round3_findings
        round_data["round_3"] = {
            agent: [f.model_dump() for f in findings]
            for agent, findings in round3_findings.items()
        }
        self.working_memory.set(session_id, {"round3_findings": round3_findings})
        logger.info(
            "[%s] Round 3 complete: %d total findings",
            session_id,
            sum(len(v) for v in round3_findings.values()),
        )

        # ── Flatten findings for synthesis ───────────────────
        flat_by_round: dict[int, list[Finding]] = {}
        for r in (1, 2, 3):
            flat: list[Finding] = []
            for agent_findings in all_findings.get(r, {}).values():
                flat.extend(agent_findings)
            flat_by_round[r] = flat

        # ── Synthesis ────────────────────────────────────────
        logger.info("[%s] Running synthesis", session_id)
        report = synthesize(flat_by_round)
        report.session_id = session_id
        round_data["report"] = report.model_dump()

        # Update working memory
        self.working_memory.set(
            session_id,
            {
                "status": "completed",
                "report": report.model_dump(),
            },
        )

        # ── Persist to episodic memory ───────────────────────
        await self._save_episodic(session_id, code, all_findings, report)

        # ── Check for semantic consolidation ─────────────────
        await self._check_consolidation(session_id)

        logger.info("[%s] Council completed successfully", session_id)
        return report, session_id, round_data

    # ──────────────────────────────────────────────
    #  Internal: run a single round
    # ──────────────────────────────────────────────

    async def _run_round(
        self,
        code: str,
        round_num: int,
        context_findings: dict[str, list[Finding]] | None,
        semantic_context: list[str] | None = None,
        image_url: str | None = None,
    ) -> dict[str, list[Finding]]:
        """Run one round across all agents in parallel."""
        # Build context list for each agent (findings from other agents)
        context_per_agent: dict[str, list[dict[str, Any]]] = {}
        if context_findings:
            for agent_name in self.agents:
                others_context: list[dict[str, Any]] = []
                for other_name, other_findings in context_findings.items():
                    if other_name != agent_name:
                        for f in other_findings:
                            others_context.append(f.model_dump())
                context_per_agent[agent_name] = others_context
        else:
            context_per_agent = {
                name: [] for name in self.agents
            }

        # Add semantic context if available
        code_with_context = code
        if semantic_context:
            code_with_context = (
                "### Contexto de memoria (patrones previos):\n"
                + "\n".join(f"- {p}" for p in semantic_context)
                + "\n\n### Código a revisar:\n\n"
                + code
            )

        # Call all agents in parallel
        tasks: dict[str, asyncio.Task[list[Finding]]] = {}
        for name, agent in self.agents.items():
            ctx = context_per_agent.get(name, [])
            is_vision = name == "vision"

            if is_vision and image_url:
                # Vision agent gets the image URL
                tasks[name] = asyncio.create_task(
                    agent.analyze(
                        code=code_with_context,
                        context=ctx,
                        round=round_num,
                        image_url=image_url,
                    )
                )
            else:
                tasks[name] = asyncio.create_task(
                    agent.analyze(
                        code=code_with_context,
                        context=ctx,
                        round=round_num,
                    )
                )

        results: dict[str, list[Finding]] = {}
        for name, task in tasks.items():
            try:
                results[name] = await task
            except Exception:
                logger.exception(
                    "Agent '%s' failed in round %d", name, round_num
                )
                results[name] = []

        return results

    # ──────────────────────────────────────────────
    #  Memory operations
    # ──────────────────────────────────────────────

    async def _retrieve_semantic_context(self, code: str) -> list[str]:
        """Retrieve relevant semantic patterns for the code context."""
        try:
            async with async_session_factory() as session:
                mgr = SemanticMemoryManager(session)
                patterns = await mgr.retrieve_relevant(code)
                return [p.pattern_text for p in patterns]
        except Exception:
            logger.exception("Failed to retrieve semantic context")
            return []

    async def _save_episodic(
        self,
        session_id: str,
        code: str,
        all_findings: dict[int, dict[str, list[Finding]]],
        report: Report,
    ) -> None:
        """Save the session to episodic memory."""
        try:
            # Flatten all findings
            flat: list[dict[str, Any]] = []
            for round_num, agent_dict in all_findings.items():
                for agent_name, findings_list in agent_dict.items():
                    for f in findings_list:
                        d = f.model_dump()
                        d["ronda"] = round_num
                        flat.append(d)

            async with async_session_factory() as session:
                mgr = EpisodicMemoryManager(session)
                await mgr.save(
                    session_id=session_id,
                    code=code,
                    findings=flat,
                )
        except Exception:
            logger.exception("Failed to save episodic memory for %s", session_id)

    async def _check_consolidation(self, session_id: str) -> None:
        """Check if any patterns should be promoted to semantic memory."""
        try:
            async with async_session_factory() as session:
                consolidator = Consolidator(
                    episodic_mgr=EpisodicMemoryManager(session),
                    semantic_mgr=SemanticMemoryManager(session),
                )
                await consolidator.run(session_id)
        except Exception:
            logger.exception("Consolidation check failed for %s", session_id)
