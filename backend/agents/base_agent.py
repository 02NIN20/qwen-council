"""Base class for all council agents.

Provides:
- OpenAI-compatible async call to Qwen Cloud API
- Prompt construction helpers for Inverted Pyramid + Given-New
- Abstract `analyze` method that subclasses must implement
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base agent.

    Parameters
    ----------
    name : str
        Unique agent identifier (e.g. "security", "architecture").
    role_description : str
        Short description of the agent's speciality.
    """

    def __init__(self, name: str, role_description: str) -> None:
        self.name = name
        self.role_description = role_description

        self._client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            timeout=settings.qwen_timeout_seconds,
        )
        self._model = settings.qwen_model

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    @abstractmethod
    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """Analyse *code* and return a list of findings.

        Parameters
        ----------
        code : str
            Source code to review.
        context : list[dict] | None
            Findings from previous rounds (other agents' output) for cross-debate.
        round : int
            Current debate round (1, 2, or 3).

        Returns
        -------
        list[Finding]
            Zero or more findings in Inverted Pyramid format.
        """
        ...

    # ──────────────────────────────────────────────
    #  Prompt helpers
    # ──────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """System prompt that sets the agent's role and output format."""
        return (
            f"You are an expert in {self.role_description}, specialised in code review. "
            "Your task is to analyse source code and find issues related to your speciality.\n\n"
            "You MUST respond ONLY with a list of findings in the following "
            "**Inverted Pyramid** format. Each finding must have this exact structure:\n\n"
            "FINDING: <one-line conclusion>\n"
            "··· Detail: <concrete evidence: file, line, code fragment>\n"
            "··· Impact: <Crítico | Alto | Medio | Bajo>\n"
            "··· Proposal: <suggested corrective action>\n\n"
            "Rules:\n"
            "- Do NOT include any text outside the specified format.\n"
            "- If you find no issues, respond ONLY with: \"NO_FINDINGS\"\n"
            "- Separate each finding with a blank line.\n"
            "- Be specific: mention actual code lines, fragments, variable/function names.\n"
            "- Use the correct impact level: Crítico (vulnerability/severe error), "
            "Alto (significant problem), Medio (important improvement), Bajo (minor suggestion)."
        )

    def _build_round_intro(self, round: int) -> str:
        """Instructions for the current debate round."""
        if round == 1:
            return (
                "### Round 1: Individual Analysis\n"
                "Analyse the code below and produce your findings independently."
            )
        elif round == 2:
            return (
                "### Round 2: Cross-Debate\n"
                "Below you will receive findings from other council agents. "
                "You must apply the **Given-New** principle: each finding must start "
                "by explicitly referencing another agent's finding.\n\n"
                "Use phrases such as:\n"
                "- \"Agreeing with [Agent] on [finding], I add that...\"\n"
                "- \"I disagree with [Agent] on [finding] because...\"\n"
                "- \"Building on [Agent]'s point about [finding], I note that...\"\n\n"
                "Keep the same Inverted Pyramid format for each finding."
            )
        elif round == 3:
            return (
                "### Round 3: Final Refinement\n"
                "You have seen all agents' arguments. Now refine your position:\n"
                "- You may **KEEP**, **MODIFY**, or **WITHDRAW** each of your findings.\n"
                "- If you modify a finding, briefly explain why.\n"
                "- If you withdraw a finding, state explicitly: \"WITHDRAWN: ...\"\n"
                "- Keep the Inverted Pyramid format for retained findings."
            )
        return ""

    def _build_context_block(self, context: list[dict[str, Any]] | None, round: int) -> str:
        """Format previous-round findings as context for the agent."""
        if not context or round == 1:
            return ""
        block_parts = ["\n### Previous round findings:\n"]
        for i, item in enumerate(context, 1):
            agent_name = item.get("agent", f"Agent {i}")
            block_parts.append(f"\n--- {agent_name} ---")
            hallazgo = item.get("hallazgo", "")
            detalle = item.get("detalle", "")
            impacto = item.get("impacto", "")
            propuesta = item.get("propuesta", "")
            block_parts.append(f"FINDING: {hallazgo}")
            if detalle:
                block_parts.append(f"··· Detail: {detalle}")
            if impacto:
                block_parts.append(f"··· Impact: {impacto}")
            if propuesta:
                block_parts.append(f"··· Proposal: {propuesta}")
        return "\n".join(block_parts)

    def _build_user_prompt(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> str:
        """Assemble the full user prompt."""
        parts = [
            self._build_round_intro(round),
            self._build_context_block(context, round),
            f"\n\n### Code to review:\n\n```\n{code}\n```",
        ]
        if round > 1:
            parts.append(
                "\n\nAdditional instructions:\n"
                "- Remember to apply Given-New in your responses.\n"
                "- Each finding must start with an explicit reference to another agent.\n"
                "- Keep the Inverted Pyramid format."
            )
        if round == 3:
            parts.append(
                "\n\nAdditional instructions:\n"
                "- Indicate whether you **KEEP**, **MODIFY**, or **WITHDRAW** each finding.\n"
                "- If WITHDRAWN, prefix with \"WITHDRAWN:\".\n"
                "- For retained findings, use the Inverted Pyramid format."
            )
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  LLM call
    # ──────────────────────────────────────────────

    async def _call_llm(self, user_prompt: str) -> str:
        """Send a chat completion request to Qwen Cloud API and return the text response."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            content: str | None = response.choices[0].message.content
            return content or "NO_FINDINGS"
        except Exception:
            logger.exception("[%s] LLM call failed", self.name)
            return "NO_FINDINGS"

    # ──────────────────────────────────────────────
    #  Response parsing
    # ──────────────────────────────────────────────

    def _parse_findings(self, text: str, round: int) -> list[Finding]:
        """Parse the LLM response into a list of Findings."""
        if not text or text.strip() == "NO_FINDINGS":
            return []

        findings: list[Finding] = []
        blocks = text.strip().split("\n\n")

        for block in blocks:
            if "WITHDRAWN:" in block:
                continue  # skip withdrawn findings
            block = block.strip()
            if not block:
                continue

            finding = self._parse_single_finding(block, round)
            if finding is not None:
                findings.append(finding)

        return findings

    def _parse_single_finding(self, block: str, round: int) -> Finding | None:
        """Parse a single Inverted Pyramid text block into a Finding."""
        lines = block.split("\n")
        finding_text = ""
        detail = ""
        impact = ""
        proposal = ""

        for line in lines:
            line = line.strip()
            if line.startswith("FINDING:"):
                finding_text = line[len("FINDING:"):].strip()
            elif line.startswith("··· Detail:") or line.startswith("···Detail:"):
                detail = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("··· Impact:") or line.startswith("···Impact:"):
                impact = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("··· Proposal:") or line.startswith("···Proposal:"):
                proposal = line.split(":", 1)[1].strip() if ":" in line else ""

        if not finding_text:
            return None

        impact = self._normalize_impact(impact)

        return Finding(
            agent=self.name,
            hallazgo=finding_text,
            detalle=detail,
            impacto=impact,
            propuesta=proposal,
            ronda=round,
        )

    @staticmethod
    def _normalize_impact(impact: str) -> str:
        """Normalize impact level to one of Crítico|Alto|Medio|Bajo."""
        normalized = impact.lower().strip()
        if "critical" in normalized or "crítico" in normalized:
            return "Crítico"
        if "high" in normalized or "alto" in normalized:
            return "Alto"
        if "medium" in normalized or "medio" in normalized:
            return "Medio"
        if "low" in normalized or "bajo" in normalized:
            return "Bajo"
        return "Medio"
