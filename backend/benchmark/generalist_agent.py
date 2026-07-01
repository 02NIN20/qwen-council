"""Generalist agent — single-agent baseline that covers ALL review domains.

This agent acts as the baseline for the benchmark. It receives the same code
but reviews it across ALL categories (security, architecture, quality,
performance, UX, vision) in a single pass, without specialisation or debate.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from backend.config import settings
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class GeneralistAgent:
    """Single-pass generalist code reviewer (baseline for benchmarks).

    Parameters
    ----------
    model : str | None
        Override model name (defaults to settings.qwen_model).
    """

    def __init__(self, model: str | None = None) -> None:
        self.name = "generalist"
        self._model = model or settings.qwen_model
        self._client = AsyncOpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            timeout=settings.qwen_timeout_seconds,
        )

    async def analyze(self, code: str) -> list[Finding]:
        """Analyse *code* across ALL domains in a single pass.

        Parameters
        ----------
        code : str
            Source code to review.

        Returns
        -------
        list[Finding]
            Findings across all categories, in Inverted Pyramid format.
        """
        system_prompt = (
            "You are a senior code reviewer with deep expertise in ALL of the following domains:\n"
            "1. SECURITY — OWASP Top 10, SQL injection, XSS, hardcoded secrets, auth flaws\n"
            "2. ARCHITECTURE — coupling, cohesion, design patterns, SOLID principles, scalability\n"
            "3. QUALITY — dead code, cyclomatic complexity, test coverage, conventions\n"
            "4. PERFORMANCE — N+1 queries, memory leaks, inefficient algorithms, caching\n"
            "5. UX / ACCESSIBILITY — ARIA attributes, keyboard navigation, colour contrast\n"
            "6. VISUAL / UI — layout issues, responsive design, CSS anomalies\n\n"
            "You MUST cover ALL 6 domains in your review. Do not skip any.\n\n"
            "Respond ONLY with a list of findings in the following **Inverted Pyramid** format. "
            "Each finding must have this exact structure:\n\n"
            "FINDING: <one-line conclusion>\n"
            "··· Detail: <concrete evidence with EXACT line numbers, code snippet, CWE reference if applicable>\n"
            "··· Impact: <Critical | High | Medium | Low>\n"
            "··· Proposal: <step-by-step corrective action with BEFORE/AFTER code example>\n\n"
            "Rules:\n"
            "- Do NOT include any text outside the specified format.\n"
            "- If you find no issues, respond ONLY with: \"NO_FINDINGS\"\n"
            "- Separate each finding with a blank line.\n"
            "- Use correct impact level: Critical (exploitable vulnerability/severe bug), "
            "High (significant issue), Medium (important improvement), Low (minor suggestion).\n"
            "- CRITICAL: Always include EXACT line numbers and the actual problematic code.\n"
            "- CRITICAL: In Proposal, show BEFORE (problematic code) and AFTER (fixed code).\n"
            "- CRITICAL: Reference CWE identifiers when applicable (e.g., CWE-89 for SQL injection)."
        )

        user_prompt = (
            "### Code to review:\n\n"
            f"```\n{code}\n```\n\n"
            "Review this code across ALL 6 domains (security, architecture, quality, "
            "performance, UX, visual/UI). Leave no domain unexplored."
        )

        if not settings.qwen_api_key:
            logger.error("GeneralistAgent: Qwen API key is not set!")
            return []

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            content: str | None = response.choices[0].message.content
            return self._parse_findings(content or "NO_FINDINGS")
        except Exception as e:
            logger.error(
                "GeneralistAgent LLM call failed: %s: %s",
                type(e).__name__, str(e)[:200],
            )
            return []

    # ------------------------------------------------------------------
    #  Parsing (same logic as BaseAgent but simplified for single-pass)
    # ------------------------------------------------------------------

    def _parse_findings(self, text: str) -> list[Finding]:
        """Parse the LLM response into a list of Findings."""
        if not text or text.strip() == "NO_FINDINGS":
            return []

        findings: list[Finding] = []
        blocks = text.strip().split("\n\n")

        for block in blocks:
            block = block.strip()
            if not block or "WITHDRAWN:" in block:
                continue
            finding = self._parse_single_finding(block)
            if finding is not None:
                findings.append(finding)

        return findings

    def _parse_single_finding(self, block: str) -> Finding | None:
        """Parse a single Inverted Pyramid text block into a Finding."""
        lines = block.split("\n")
        title = ""
        detail = ""
        impact = ""
        proposal = ""

        for line in lines:
            line = line.strip()
            if line.startswith("FINDING:"):
                title = line[len("FINDING:"):].strip()
            elif line.startswith("··· Detail:") or line.startswith("···Detail:"):
                detail = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("··· Impact:") or line.startswith("···Impact:"):
                impact = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("··· Proposal:") or line.startswith("···Proposal:"):
                proposal = line.split(":", 1)[1].strip() if ":" in line else ""

        if not title:
            return None

        impact = self._normalize_impact(impact)

        return Finding(
            agent="generalist",
            title=title,
            detail=detail,
            impact=impact,
            proposal=proposal,
            round_num=0,
        )

    @staticmethod
    def _normalize_impact(impact: str) -> str:
        """Normalise impact level to one of Critical|High|Medium|Low."""
        norm = impact.lower().strip()
        if "critical" in norm or "crítico" in norm:
            return "Critical"
        if "high" in norm or "alto" in norm:
            return "High"
        if "medium" in norm or "medio" in norm:
            return "Medium"
        if "low" in norm or "bajo" in norm:
            return "Low"
        return "Medium"
