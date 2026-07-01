"""Vision agent — analyses UI screenshots, architecture diagrams, and code visuals.

Uses Qwen-VL (multimodal) to find issues in UI/UX, diagram inconsistencies,
accessibility problems, and visual regressions from screenshots or wireframes.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class VisionAgent(BaseAgent):
    """Agent specialised in visual analysis of UIs, diagrams, and screenshots.

    NOTE: This agent does NOT store per-request state on ``self`` because
    ``CouncilOrchestrator`` holds agents as singletons. All per-request
    data (``image_url``) is passed as a parameter to avoid race conditions.
    """

    def __init__(self) -> None:
        # Use the VL model for vision, fall back to the default text model
        self._vision_model = "qwen-vl-max"
        super().__init__(
            name="vision",
            role_description=(
                "visual design, UI consistency, and accessibility. I see the big picture and the tiny details in any topic."
            ),
        )

    def _build_system_prompt(self) -> str:
        """Extended system prompt that covers both code and visual analysis."""
        return (
            f"You are an expert in {self.role_description}, specialised in visual code review. "
            "Your task is to analyse source code AND any provided screenshots or diagrams "
            "to find issues related to visual design, accessibility, and UI/UX.\n\n"
            "You MUST respond ONLY with a list of findings in the following "
            "**Inverted Pyramid** format. Each finding must have this exact structure:\n\n"
            "FINDING: <one-line conclusion>\n"
            "··· Detail: <concrete evidence: file, line, code fragment or visual element>\n"
            "··· Impact: <Critical | High | Medium | Low>\n"
            "··· Proposal: <suggested corrective action>\n\n"
            "Rules:\n"
            "- Do NOT include any text outside the specified format.\n"
            "- If you find no issues, respond ONLY with: \"NO_FINDINGS\"\n"
            "- Separate each finding with a blank line.\n"
            "- Be specific: mention actual code lines, visual elements, or UI components.\n"
            "- For visual issues, describe what you see and why it is problematic.\n"
            "- Use the correct impact level: Critical (severe problem), "
            "High (significant issue), Medium (important improvement), Low (minor suggestion)."
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
        image_url: str | None = None,
    ) -> list[Finding]:
        """Analyse code and/or image for visual/UX issues.

        Parameters
        ----------
        code : str
            Source code to review.
        context : list[dict] | None
            Findings from previous rounds for cross-debate.
        round : int
            Current debate round (1, 2, or 3).
        image_url : str | None
            URL or base64 data URI of a screenshot/diagram to analyse.

        Returns
        -------
        list[Finding]
            Zero or more findings in Inverted Pyramid format.
        """
        user_prompt = self._build_user_prompt(code, context, round)
        raw = await self._call_llm(user_prompt, image_url=image_url)
        return self._parse_findings(raw, round)

    async def _call_llm(self, user_prompt: str, image_url: str | None = None) -> str:
        """Call Qwen-VL with multimodal content if an image is available.

        Parameters
        ----------
        user_prompt : str
            The assembled prompt for the LLM.
        image_url : str | None
            Image URL to include as multimodal content. Passed directly (not
            stored on ``self``) to avoid race conditions with shared agents.
        """
        try:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": self._build_system_prompt()},
            ]

            # Build user message — text-only or text + image
            if image_url:
                # Multimodal content: text + image
                user_content: list[dict[str, Any]] = [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url},
                    },
                ]
                messages.append({"role": "user", "content": user_content})
                model = self._vision_model
            else:
                # Text-only fallback
                messages.append({"role": "user", "content": user_prompt})
                model = self._model

            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
            )
            content: str | None = response.choices[0].message.content
            return content or "NO_FINDINGS"
        except Exception:
            logger.exception("[%s] LLM call failed", self.name)
            return "NO_FINDINGS"
