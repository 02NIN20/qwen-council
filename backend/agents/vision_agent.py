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
        self._vision_model = "qwen-vl-max"
        super().__init__(
            name="vision",
            role_description=(
                "visual design, UI consistency, and accessibility. I see the big picture and the tiny details in any topic."
            ),
        )

    def _build_system_prompt(self) -> str:
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
        """Analyse code and/or image for visual/UX issues."""
        user_prompt = self._build_user_prompt(code, context, round)
        raw = await self._call_llm(user_prompt, image_url=image_url)
        return self._parse_findings(raw, round)

    async def answer_question(self, question: str, context: str | None = None, image_url: str | None = None) -> str:
        """Answer a question, using the vision model if an image is provided.

        Overrides BaseAgent.answer_question() to support multimodal image analysis.
        Called by the chat endpoint when a user uploads an image.

        Parameters
        ----------
        question : str
            The user's question about the image.
        context : str | None
            Optional additional context.
        image_url : str | None
            Data URI of an image (e.g. "data:image/jpeg;base64,...").

        Returns
        -------
        str
            The agent's answer based on visual analysis.
        """
        system_prompt = (
            f"You are an expert in {self.role_description}. "
            "Analyse the provided image and answer the user's question based on what you see. "
            "Be specific and detailed about visual elements, diagrams, screenshots, or UI components. "
            "If you cannot see an image, explain what you would need to see."
        )

        user_text = f"### Question:\n{question}\n"
        if context:
            user_text += f"\n### Context:\n{context}\n"

        try:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
            ]

            if image_url:
                user_content: list[dict[str, Any]] = [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]
                messages.append({"role": "user", "content": user_content})
                model = self._vision_model
            else:
                messages.append({"role": "user", "content": user_text})
                model = self._model

            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
            )
            if hasattr(response, 'usage') and response.usage:
                self._last_token_usage = {
                    "input_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "output_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0),
                }
            return response.choices[0].message.content or "I could not analyse the image."
        except Exception:
            logger.exception("[%s] Vision chat failed", self.name)
            return "I encountered an error analysing the image."

    async def _call_llm(self, user_prompt: str, image_url: str | None = None) -> str:
        """Call Qwen-VL with multimodal content if an image is available."""
        try:
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": self._build_system_prompt()},
            ]

            if image_url:
                user_content: list[dict[str, Any]] = [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]
                messages.append({"role": "user", "content": user_content})
                model = self._vision_model
            else:
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
