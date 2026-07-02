"""Council orchestrator — runs the multi-agent debate and produces the final report.

Flow:
  1. Round 1: All core agents analyse the code independently (parallel).
  2. Round 2: Each agent receives the findings from Round 1 and debates (parallel).
  3. Round 3: Each agent receives the debates from Round 2 and refines (parallel).
  4. Synthesis: Consolidates findings, counts votes, determines consensus.
  5. Round 4 (Negotiation, if needed): Agents with low-consensus findings debate
     — each states their position, rebuts the other, and either converges or
     agrees to disagree.  The transcript becomes part of the final report.
  6. Memory: Save episodic memory, check for semantic consolidation.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

from backend.agents.core.coordinator_agent import CoordinatorAgent
from backend.agents.core.analyst_agent import AnalystAgent
from backend.agents.core.architect_agent import ArchitectAgent
from backend.agents.core.engineer_agent import EngineerAgent
from backend.agents.core.critic_agent import CriticAgent
from backend.agents.core.researcher_agent import ResearcherAgent
from backend.config import settings
from backend.council.budget import BudgetConfig, TokenBudget, TokenUsage
from backend.council.synthesizer import synthesize
from backend.memory.consolidator import Consolidator
from backend.memory.episodic_memory import EpisodicMemoryManager
from backend.memory.semantic_memory import SemanticMemoryManager
from backend.memory.working_memory import WorkingMemory
from backend.models.db import async_session_factory
from backend.models.schemas import FileContent, Finding, Report

logger = logging.getLogger(__name__)


class CouncilOrchestrator:
    """Manages the full council debate lifecycle."""

    def __init__(self) -> None:
        self.agents = {
            "coordinator": CoordinatorAgent(),
            "analyst": AnalystAgent(),
            "architect": ArchitectAgent(),
            "engineer": EngineerAgent(),
            "critic": CriticAgent(),
            "researcher": ResearcherAgent(),
        }
        self.working_memory = WorkingMemory()
        # Per-review token budget (set at the start of each run_council / stream_council)
        self.budget: TokenBudget | None = None

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _build_multi_file_context(files: list[FileContent]) -> str:
        """Build a structured multi-file context string with file headers."""
        if not files:
            return ""
        parts = []
        for f in files:
            lang = f.language or f.filename.split(".")[-1] if "." in f.filename else ""
            parts.append(f"### File: {f.filename}")
            if lang:
                parts.append(f"```{lang}")
            else:
                parts.append("```")
            parts.append(f.content)
            parts.append("```")
            parts.append("")
        return "\n".join(parts)

    async def run_council(
        self,
        code: str,
        session_id: str | None = None,
        image_files: list[Any] | None = None,
        files: list[FileContent] | None = None,
        instruction: str | None = None,
        mode: str = "full",
        budget_config: BudgetConfig | None = None,
    ) -> tuple[Report, str, dict[str, Any]]:
        """Execute the full council debate.
        Parameters
        ----------
        code : str
            Source code to review.
        session_id : str | None
            Existing session ID for memory continuity.
        image_files : list[ImageFile] | None
            Optional image files for visual analysis (screenshots, diagrams).
        files : list[FileContent] | None
            Optional list of source files for multi-file review.
        instruction : str | None
            Optional review instruction.
        mode : str
            "full" (6 agents, 4 rounds) or "light" (3 agents, 2 rounds).

        Returns
        -------
        tuple[Report, str, dict[str, Any]]
            (final_report, session_id, round_data)
        """
        if not session_id:
            session_id = f"ses-{uuid.uuid4().hex[:12]}"

        # Initialise per-review token budget from the mode (or explicit config)
        budget_config = budget_config or BudgetConfig.from_mode(mode)
        self.budget = TokenBudget(budget_config)
        logger.info(
            "[%s] Token budget: max_in=%d, max_out=%d, max_cost=$%.2f, max_rounds=%d",
            session_id,
            budget_config.max_input_tokens,
            budget_config.max_output_tokens,
            budget_config.max_cost_usd,
            budget_config.max_rounds,
        )

        # Determine agents and rounds based on mode
        if mode == "light":
            active_agents = {k: self.agents[k] for k in ("critic", "analyst", "architect")}
            max_rounds = min(2, budget_config.max_rounds)
            logger.info("[%s] Light mode: 3 agents, %d rounds", session_id, max_rounds)
        else:
            active_agents = self.agents
            max_rounds = min(3, budget_config.max_rounds)
            logger.info("[%s] Full mode: 6 agents, %d rounds", session_id, max_rounds)

        # Initialize round data for frontend tracing
        round_data: dict[str, Any] = {}

        # Build full code context from files if provided
        if files:
            round_data["files"] = [
                {"filename": f.filename, "size": len(f.content), "language": f.language or (f.filename.split(".")[-1] if "." in f.filename else "text")}
                for f in files
            ]
            if not code.strip():
                code = self._build_multi_file_context(files)
            else:
                file_context = self._build_multi_file_context(files)
                code = file_context + "\n\n### Additional code:\n\n" + code
        else:
            round_data["files"] = [{"filename": "source.txt", "size": len(code), "language": "text"}]

        # Store context preview (truncated for display)
        round_data["context_preview"] = code[:3000] + ("..." if len(code) > 3000 else "")

        # Store instruction for frontend visibility
        if instruction:
            round_data["instruction"] = instruction
            # Prepend instruction to the code so all agents see it as a user directive
            instruction_block = f"### User instructions:\n{instruction}\n\n### Code to review:\n\n"
            code = instruction_block + code
            # Update context_preview too
            round_data["context_preview"] = code[:3000] + ("..." if len(code) > 3000 else "")

        # Store in working memory
        self.working_memory.set(session_id, {"code": code, "status": "in_progress"})

        # Retrieve relevant semantic memory patterns
        semantic_patterns = await self._retrieve_semantic_context(code)

        # Convert image files to data URIs — inject directly into code
        # context so ALL agents see it (no longer routed to a "vision" agent).
        image_url = None
        if image_files:
            img = image_files[0]
            image_url = f"data:{img.mime_type};base64,{img.content}"
            # Prepend image description to code for all agents
            image_block = (
                f"\n### User uploaded image: {img.filename} ({img.mime_type})\n"
                f"The image is available at the following data URI. "
                f"Analyse it for visual issues, UI problems, diagrams, "
                f"screenshots, or any relevant information.\n"
                f"Image data: {image_url[:200]}...\n"
            )
            code = image_block + "\n\n" + code
            round_data["images"] = [{"filename": img.filename, "mime_type": img.mime_type}]

        all_findings: dict[int, list[Finding]] = {}

        # ── Round 1: Individual analysis ──────────────────────
        logger.info("[%s] Starting Round 1: Individual analysis", session_id)
        # Early-exit guard: budget check at start of every round
        if self.budget and self.budget.is_exhausted():
            logger.warning("[%s] Budget exhausted before round 1", session_id)

        round1_findings = await self._run_round(
            code=code,
            round_num=1,
            context_findings=None,
            semantic_context=semantic_patterns,
            image_url=image_url,  # kept for BW compat, injected in code above
            agents=active_agents,
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
        # Early-exit: budget check + skip if Round 1 found nothing
        r1_total = sum(len(v) for v in round1_findings.values())
        if self.budget and self.budget.is_exhausted():
            logger.warning("[%s] Budget exhausted, skipping Round 2", session_id)
        elif r1_total == 0:
            logger.info("[%s] No findings in Round 1, skipping Round 2", session_id)
        else:
            logger.info("[%s] Starting Round 2: Cross-debate", session_id)
            round2_findings = await self._run_round(
                code=code,
                round_num=2,
                context_findings=round1_findings,
                semantic_context=semantic_patterns,
                image_url=image_url,
                agents=active_agents,
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

        # ── Round 3: Refinement (full mode only) ─────────────
        if max_rounds >= 3:
            # Early-exit: budget check + skip if Round 2 found nothing
            r2_total = sum(len(v) for v in all_findings.get(2, {}).values())
            if self.budget and self.budget.is_exhausted():
                logger.warning("[%s] Budget exhausted, skipping Round 3", session_id)
            elif r2_total == 0:
                logger.info("[%s] No findings in Round 2, skipping Round 3", session_id)
            else:
                logger.info("[%s] Starting Round 3: Refinement", session_id)
                round3_findings = await self._run_round(
                    code=code,
                    round_num=3,
                    context_findings=round2_findings,
                    semantic_context=semantic_patterns,
                    image_url=image_url,
                    agents=active_agents,
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
        for r in range(1, max_rounds + 1):
            flat: list[Finding] = []
            for agent_findings in all_findings.get(r, {}).values():
                flat.extend(agent_findings)
            flat_by_round[r] = flat

        # ── Synthesis ────────────────────────────────────────
        logger.info("[%s] Running synthesis", session_id)

        # Collect token usage from active agents
        agent_token_usage: dict[str, Any] = {}
        total_input = 0
        total_output = 0
        for name, agent in active_agents.items():
            usage = agent.get_token_usage()
            if usage:
                agent_token_usage[name] = usage
                total_input += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)

        # Use the per-review TokenBudget for accurate cost (qwen-plus pricing)
        from backend.council.budget import QWEN_PLUS_INPUT_PER_1K, QWEN_PLUS_OUTPUT_PER_1K
        estimated_cost = (total_input / 1000) * QWEN_PLUS_INPUT_PER_1K + (total_output / 1000) * QWEN_PLUS_OUTPUT_PER_1K

        token_data: dict[str, Any] = {
            "per_agent": agent_token_usage,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost_usd": round(estimated_cost, 4),
            "model": settings.llm_model,
        }
        if self.budget is not None:
            token_data["budget"] = self.budget.summary()

        report = await synthesize(
            flat_by_round,
            code_context=code[:2000],  # pass truncated code for LLM context
            session_id=session_id,
            token_usage=token_data,
        )
        round_data["report"] = report.model_dump()

        # ── Round 4: Negotiation (full mode only) ────────────
        if max_rounds >= 4:
            negotiation_transcript = await self._run_negotiation_round(
                session_id=session_id,
                code=code,
                report_findings=report.findings,
                all_rounds_findings=all_findings,
            )
            if negotiation_transcript:
                round_data["round_4_negotiation"] = negotiation_transcript
                logger.info(
                    "[%s] Round 4 negotiation complete: %d disagreements debated",
                    session_id,
                    len(negotiation_transcript),
                )
            else:
                logger.info("[%s] No negotiation needed — all findings have strong consensus", session_id)

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
    #  Streaming (SSE) variant
    # ──────────────────────────────────────────────

    async def stream_council(
        self,
        code: str,
        session_id: str | None = None,
        image_files: list[Any] | None = None,
        files: list[FileContent] | None = None,
        instruction: str | None = None,
        mode: str = "full",
        budget_config: BudgetConfig | None = None,
    ) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
        """Async generator that yields ``(event_type, data)`` tuples for SSE streaming.

        Mirrors :meth:`run_council` but yields progress events at each step so
        callers can stream real-time updates to the frontend via Server-Sent Events.

        Events yielded
        --------------
        * ``round_start``       — before each debate round
        * ``agent_start``       — before calling a single agent
        * ``agent_complete``    — after an agent returns findings
        * ``agent_error``       — if an agent call fails
        * ``round_complete``    — after all agents in a round finish
        * ``synthesis_complete`` — after the synthesizer finishes
        * ``negotiation_start``  — if there are low-consensus findings
        * ``negotiation_complete`` — after negotiation finishes
        * ``complete``          — final event with the full report and session ID
        * ``error``             — if the entire council fails (terminal)
        """
        if not session_id:
            session_id = f"ses-{uuid.uuid4().hex[:12]}"

        # Initialise per-review token budget
        budget_config = budget_config or BudgetConfig.from_mode(mode)
        self.budget = TokenBudget(budget_config)
        logger.info(
            "[%s] Token budget: max_in=%d, max_out=%d, max_cost=$%.2f, max_rounds=%d",
            session_id,
            budget_config.max_input_tokens,
            budget_config.max_output_tokens,
            budget_config.max_cost_usd,
            budget_config.max_rounds,
        )

        # Determine agents based on mode
        if mode == "light":
            active_agents = {k: self.agents[k] for k in ("critic", "analyst", "architect")}
            total_rounds = min(2, budget_config.max_rounds)
            logger.info("[%s] Light mode (stream): 3 agents, %d rounds", session_id, total_rounds)
        else:
            active_agents = self.agents
            total_rounds = min(3, budget_config.max_rounds)
            logger.info("[%s] Full mode (stream): 6 agents, %d rounds", session_id, total_rounds)

        # Build full code context from files if provided
        if files:
            if not code.strip():
                code = self._build_multi_file_context(files)
            else:
                file_context = self._build_multi_file_context(files)
                code = file_context + "\n\n### Additional code:\n\n" + code

        # Convert image files to data URIs — inject into code for ALL agents
        image_url = None
        if image_files:
            img = image_files[0]
            image_url = f"data:{img.mime_type};base64,{img.content}"
            image_block = (
                f"\n### User uploaded image: {img.filename} ({img.mime_type})\n"
                f"The image data is: {image_url[:200]}...\n"
                f"Analyse it for visual issues, UI problems, diagrams, or "
                f"screenshots.\n"
            )
            code = image_block + "\n\n" + code

        # Prepend instruction if provided
        if instruction:
            instruction_block = f"### User instructions:\n{instruction}\n\n### Code to review:\n\n"
            code = instruction_block + code

        # Store in working memory
        self.working_memory.set(session_id, {"code": code, "status": "in_progress"})

        # Retrieve relevant semantic memory patterns
        semantic_patterns = await self._retrieve_semantic_context(code)

        all_findings: dict[int, dict[str, list[Finding]]] = {}

        try:
            # ── Rounds ──────────────────────────────────────────────
            prev_round_total = 0
            for round_num in range(1, total_rounds + 1):
                # Early-exit: if the budget is exhausted, stop debating
                if self.budget and self.budget.is_exhausted():
                    logger.warning(
                        "[%s] Budget exhausted before round %d, stopping",
                        session_id, round_num,
                    )
                    yield ("budget_exhausted", {
                        "round": round_num,
                        "remaining": self.budget.remaining(),
                    })
                    break
                yield ("round_start", {"round": round_num, "total_rounds": total_rounds})
                logger.info("[%s] Starting Round %d (stream)", session_id, round_num)

                # Build context per agent (findings from other agents in previous round)
                context_per_agent: dict[str, list[dict[str, Any]]] = {}
                if round_num > 1 and (round_num - 1) in all_findings:
                    prev_findings = all_findings[round_num - 1]
                    for agent_name in active_agents:
                        others_context: list[dict[str, Any]] = []
                        for other_name, other_findings in prev_findings.items():
                            if other_name != agent_name:
                                for f in other_findings:
                                    others_context.append(f.model_dump())
                        context_per_agent[agent_name] = others_context
                else:
                    context_per_agent = {name: [] for name in active_agents}

                # Add semantic context if available
                code_with_context = code
                if semantic_patterns:
                    code_with_context = (
                        "### Memory context (previous patterns):\n"
                        + "\n".join(f"- {p}" for p in semantic_patterns)
                        + "\n\n### Code to review:\n\n"
                        + code
                    )

                # Launch all agents in parallel
                tasks: dict[str, asyncio.Task[list[Finding]]] = {}
                for name, agent in active_agents.items():
                    yield ("agent_start", {"agent": name, "round": round_num})
                    ctx = context_per_agent.get(name, [])
                    tasks[name] = asyncio.create_task(
                        self._analyze_with_retry(
                            agent=agent,
                            agent_name=name,
                            round_num=round_num,
                            code=code_with_context,
                            context=ctx,
                            image_url=image_url,  # injected in code for all agents
                        )
                    )

                # Collect results as each task completes
                round_findings: dict[str, list[Finding]] = {}
                for name, task in tasks.items():
                    try:
                        findings = await asyncio.wait_for(task, timeout=300.0)
                        round_findings[name] = findings
                        yield ("agent_complete", {
                            "agent": name,
                            "round": round_num,
                            "findings_count": len(findings),
                        })
                    except asyncio.TimeoutError:
                        logger.error(
                            "[%s] Agent '%s' timed out in round %d",
                            session_id, name, round_num,
                        )
                        round_findings[name] = []
                        yield ("agent_error", {
                            "agent": name,
                            "round": round_num,
                            "error": "Request timed out after 300 seconds",
                        })
                    except Exception as e:
                        logger.exception(
                            "[%s] Agent '%s' failed in round %d",
                            session_id, name, round_num,
                        )
                        round_findings[name] = []
                        yield ("agent_error", {
                            "agent": name,
                            "round": round_num,
                            "error": str(e)[:300],
                        })

                all_findings[round_num] = round_findings
                total_findings = sum(len(f) for f in round_findings.values())
                yield ("round_complete", {
                    "round": round_num,
                    "total_findings": total_findings,
                })
                logger.info(
                    "[%s] Round %d complete: %d findings (stream)",
                    session_id, round_num, total_findings,
                )

                # Early-exit: if a round produced no new findings, skip
                # the remaining rounds — no point debating about nothing.
                if round_num >= 2 and total_findings == prev_round_total:
                    logger.info(
                        "[%s] No new findings in round %d, stopping early",
                        session_id, round_num,
                    )
                    yield ("early_exit", {
                        "round": round_num,
                        "reason": "no_new_findings",
                        "total_findings": total_findings,
                    })
                    break
                prev_round_total = total_findings

            # ── Flatten findings for synthesis ──────────────────────
            flat_by_round: dict[int, list[Finding]] = {}
            for r in (1, 2, 3):
                flat: list[Finding] = []
                for agent_findings in all_findings.get(r, {}).values():
                    flat.extend(agent_findings)
                flat_by_round[r] = flat

            # ── Synthesis ───────────────────────────────────────────
            logger.info("[%s] Running synthesis (stream)", session_id)

            # Collect token usage from all agents
            agent_token_usage = {}
            total_input = 0
            total_output = 0
            for name, agent in self.agents.items():
                usage = agent.get_token_usage()
                if usage:
                    agent_token_usage[name] = usage
                    total_input += usage.get("input_tokens", 0)
                    total_output += usage.get("output_tokens", 0)

            estimated_cost = (total_input / 1000) * 0.004 + (total_output / 1000) * 0.012

            token_data = {
                "per_agent": agent_token_usage,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_input + total_output,
                "estimated_cost_usd": round(estimated_cost, 4),
                "model": settings.llm_model,
            }

            report = await synthesize(
                flat_by_round,
                code_context=code[:2000],
                session_id=session_id,
                token_usage=token_data,
            )
            yield ("synthesis_complete", {
                "consolidated_findings": len(report.findings),
            })

            # ── Round 4: Negotiation (low-consensus findings) ──────
            disputed_count = sum(
                1 for cf in report.findings
                if cf.consensus_level in ("Medium", "Low", "No consensus")
            )
            if disputed_count > 0:
                yield ("negotiation_start", {"disputed_count": disputed_count})

            negotiation_transcript = await self._run_negotiation_round(
                session_id=session_id,
                code=code,
                report_findings=report.findings,
                all_rounds_findings=all_findings,
            )
            if negotiation_transcript:
                yield ("negotiation_complete", {
                    "resolved": sum(
                        1 for t in negotiation_transcript
                        if t.get("resolved", False)
                    ),
                    "transcript": negotiation_transcript,
                })

            # Update working memory
            self.working_memory.set(
                session_id,
                {"status": "completed", "report": report.model_dump()},
            )

            # Persist to episodic memory
            await self._save_episodic(session_id, code, all_findings, report)

            # Check for semantic consolidation
            await self._check_consolidation(session_id)

            logger.info("[%s] Council completed successfully (stream)", session_id)

            # Final complete event with full report
            yield ("complete", {
                "session_id": session_id,
                "report": report.model_dump(),
            })

        except Exception as e:
            logger.exception("[%s] Council stream failed", session_id)
            yield ("error", {
                "message": "Council execution failed",
                "detail": str(e)[:500],
            })

    # ──────────────────────────────────────────────
    #  Internal: run a single round
    # ──────────────────────────────────────────────

    async def _analyze_with_retry(
        self,
        agent,
        agent_name: str,
        round_num: int,
        code: str,
        context: list[dict],
        image_url: str | None = None,
        max_retries: int = 2,
        timeout_seconds: int = 120,
    ) -> list[Finding]:
        """Call agent.analyze() with retry logic, exponential backoff, and timeout.

        Note: image data is now injected directly into *code* as text context,
        so ALL agents receive it without needing a special \"vision\" parameter.
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                coro = agent.analyze(
                    code=code, context=context, round=round_num
                )
                return await asyncio.wait_for(coro, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"Agent '{agent_name}' timed out after {timeout_seconds}s")
                logger.warning(
                    "[Round %d] Agent '%s' timed out after %ds (attempt %d/%d)",
                    round_num, agent_name, timeout_seconds, attempt + 1, max_retries + 1,
                )
                if attempt < max_retries:
                    await asyncio.sleep(2)
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(
                        "[Round %d] Agent '%s' failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        round_num, agent_name, attempt + 1, max_retries + 1, e, wait,
                    )
                    await asyncio.sleep(wait)
        logger.error(
            "[Round %d] Agent '%s' failed after %d attempts: %s",
            round_num, agent_name, max_retries + 1, last_error,
        )
        return []

    async def _run_round(
        self,
        code: str,
        round_num: int,
        context_findings: dict[str, list[Finding]] | None,
        semantic_context: list[str] | None = None,
        image_url: str | None = None,
        agents: dict[str, Any] | None = None,
    ) -> dict[str, list[Finding]]:
        """Run one round across all agents in parallel."""
        active = agents if agents is not None else self.agents

        # ── Domain-aware context filtering ──
        # Each agent only sees findings from agents in related domains.
        # This prevents agents from commenting outside their expertise.
        AGENT_DOMAINS: dict[str, set[str]] = {
            "critic": {"security", "quality", "validation", "style"},
            "analyst": {"patterns", "complexity", "static_analysis", "quality"},
            "architect": {"architecture", "dependencies", "scalability", "design"},
            "engineer": {"implementation", "refactoring", "optimization", "fixes"},
            "researcher": {"documentation", "best_practices", "references"},
            "coordinator": {"orchestration", "synthesis", "escalation"},
        }
        # Agents whose findings are relevant to each agent
        RELEVANT_PEERS: dict[str, set[str]] = {
            "critic": {"critic", "analyst", "engineer"},
            "analyst": {"analyst", "critic", "engineer", "architect"},
            "architect": {"architect", "analyst", "engineer"},
            "engineer": {"engineer", "critic", "analyst", "architect"},
            "researcher": {"researcher", "analyst", "architect"},
            "coordinator": {"critic", "analyst", "architect", "engineer", "researcher"},
        }

        # Build context list for each agent (findings from other agents, domain-filtered)
        context_per_agent: dict[str, list[dict[str, Any]]] = {}
        if context_findings:
            for agent_name in active:
                others_context: list[dict[str, Any]] = []
                relevant = RELEVANT_PEERS.get(agent_name, set(active.keys()))
                for other_name, other_findings in context_findings.items():
                    if other_name != agent_name and other_name in relevant:
                        for f in other_findings:
                            others_context.append(f.model_dump())
                context_per_agent[agent_name] = others_context
        else:
            context_per_agent = {
                name: [] for name in active
            }

        # Add semantic context if available
        code_with_context = code
        if semantic_context:
            code_with_context = (
                "### Memory context (previous patterns):\n"
                + "\n".join(f"- {p}" for p in semantic_context)
                + "\n\n### Code to review:\n\n"
                + code
            )

        # Call all agents in parallel with retry
        tasks: dict[str, asyncio.Task[list[Finding]]] = {}
        for name, agent in active.items():
            ctx = context_per_agent.get(name, [])
            tasks[name] = asyncio.create_task(
                self._analyze_with_retry(
                    agent=agent,
                    agent_name=name,
                    round_num=round_num,
                    code=code_with_context,
                    context=ctx,
                    image_url=image_url,  # injected in code for all agents
                )
            )

        results: dict[str, list[Finding]] = {}
        for name, task in tasks.items():
            try:
                results[name] = await asyncio.wait_for(task, timeout=300.0)
            except asyncio.TimeoutError:
                logger.error("Agent '%s' timed out in round %d", name, round_num)
                results[name] = []
            except Exception:
                logger.exception("Unexpected error waiting for agent '%s' in round %d", name, round_num)
                results[name] = []

        return results

    # ──────────────────────────────────────────────
    #  Round 4: Negotiation (dialogue for low-consensus findings)
    # ──────────────────────────────────────────────

    async def _run_negotiation_round(
        self,
        session_id: str,
        code: str,
        report_findings: list[Any],
        all_rounds_findings: dict[int, Any],
    ) -> list[dict[str, Any]]:
        """Run a negotiation round for findings with low consensus.

        For findings where consensus_level is "Medium", "Low", or "No consensus",
        the disagreeing agents are identified and each is asked to:
          1. State their position with evidence
          2. Rebut the opposing position
          3. Either converge or state why they maintain their position

        Returns a list of negotiation transcripts, one per disputed finding.
        """
        # Find low-consensus findings
        disputed = [
            cf for cf in report_findings
            if getattr(cf, "consensus_level", "High") in ("Medium", "Low", "No consensus")
        ]

        if not disputed:
            return []

        # Find which agents participated in each disputed finding's discussion
        transcripts: list[dict[str, Any]] = []

        for cf in disputed:
            votes: dict[str, str] = getattr(cf, "votes", {})
            voting_agents = list(votes.keys())

            if len(voting_agents) < 2:
                continue

            # Group agents by severity position
            position_groups: dict[str, list[str]] = {}
            for agent_name, severity in votes.items():
                position_groups.setdefault(severity, []).append(agent_name)

            if len(position_groups) < 2:
                continue  # all agree on severity, consensus issue is elsewhere

            # Build the negotiation prompt with both positions
            positions_text = "\n".join(
                f"  - {', '.join(agents)} says severity is **{sev}**"
                for sev, agents in position_groups.items()
            )

            # For each group, ask an agent to defend
            debate_log: list[dict[str, str]] = []
            for sev, agents in position_groups.items():
                if not agents:
                    continue
                chosen = agents[0]
                try:
                    rebuttal = await self._call_negotiation(
                        agent_name=chosen,
                        agent=self.agents.get(chosen),
                        finding_title=cf.title,
                        code=code,
                        positions=positions_text,
                        my_severity=sev,
                        my_votes=votes,
                    )
                    debate_log.append({
                        "agent": chosen,
                        "severity": sev,
                        "argument": rebuttal[:500],  # truncate for storage
                    })
                except Exception:
                    logger.exception(
                        "Negotiation failed for agent '%s' on finding '%s'",
                        chosen, cf.title[:50],
                    )

            if debate_log:
                transcript = {
                    "finding_title": cf.title,
                    "impact": cf.impact,
                    "disputed_severities": {s: a for s, a in position_groups.items()},
                    "debate": debate_log,
                    "resolved": len(debate_log) >= 2 and any(
                        "converge" in d.get("argument", "").lower()
                        or "agree" in d.get("argument", "").lower()
                        for d in debate_log
                    ),
                }

                # If a convergence is detected, update can be recorded
                if transcript["resolved"]:
                    final_severity = self._resolve_negotiation(debate_log)
                    transcript["resolved_severity"] = final_severity
                else:
                    transcript["resolved_severity"] = None

                transcripts.append(transcript)

        return transcripts

    async def _call_negotiation(
        self,
        agent_name: str,
        agent,
        finding_title: str,
        code: str,
        positions: str,
        my_severity: str,
        my_votes: dict[str, str],
    ) -> str:
        """Call a single agent to argue its position in a negotiation."""
        if agent is None:
            return "Agent unavailable"

        from backend.agents.base_agent import BaseAgent
        if not isinstance(agent, BaseAgent):
            return "Agent type not supported"

        prompt = (
            f"### Negotiation Round — Disputed Finding\n\n"
            f"**Finding:** {finding_title}\n\n"
            f"**Your position:** {my_severity}\n\n"
            f"**Current positions:\n{positions}\n\n"
            f"### Code being reviewed:\n```\n{code[:2000]}\n```\n\n"
            "Please do the following:\n"
            "1. **STATE YOUR POSITION**: Defend why this finding should be "
            f"severity **{my_severity}** with specific evidence from the code.\n"
            "2. **REBUT OPPOSITION**: Address the opposing agents' arguments. "
            "Explain why their severity assessment is incorrect.\n"
            "3. **CONVERGE OR MAINTAIN**: Either adjust your position (if the "
            "opposing evidence is convincing) OR maintain your original position "
            "with your strongest justification.\n\n"
            "Respond in this format:\n"
            "POSITION: <your stance>\n"
            "EVIDENCE: <code evidence>\n"
            "REBUTTAL: <counter-argument>\n"
            "CONCLUSION: <Converge on X | Maintain Y>\n"
        )

        user_prompt = (
            f"### Negotiation request for {agent_name}\n\n{prompt}"
        )

        response = await agent._call_llm(user_prompt)
        return response or "No response"

    @staticmethod
    def _resolve_negotiation(
        debate_log: list[dict[str, str]],
    ) -> str | None:
        """Resolve negotiation outcome based on debate log.

        If agents converged, return the agreed severity.
        If not, return the most common position.
        """
        from collections import Counter

        conclusions = []
        for entry in debate_log:
            arg = entry.get("argument", "")
            # Look for convergence signal
            if "converge on" in arg.lower():
                # Extract the target severity
                for sev in ("Critical", "High", "Medium", "Low"):
                    if sev.lower() in arg.lower():
                        conclusions.append(sev)
                        break
            else:
                conclusions.append(entry.get("severity", "Medium"))

        if not conclusions:
            return None

        # Majority vote
        counter = Counter(conclusions)
        return counter.most_common(1)[0][0]

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
                        d["round_num"] = round_num
                        flat.append(d)

            async with async_session_factory() as session:
                mgr = EpisodicMemoryManager(session)
                await mgr.save(
                    session_id=session_id,
                    code=code,
                    findings={
                        "report": report.model_dump(),
                        "findings": flat,
                    },
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
