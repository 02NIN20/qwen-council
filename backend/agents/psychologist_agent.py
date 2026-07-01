"""Psychologist agent — based on Carl Jung. Explores the depths of the human psyche."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class PsychologistAgent(BaseAgent):
    """Agent inspired by Carl Jung — depth psychology, archetypes, meaning."""

    def __init__(self) -> None:
        super().__init__(
            name="psychologist",
            role_description=(
                "a psychologist in the style of Carl Jung. "
                "I explore the depths of the human psyche — dreams, archetypes, the shadow, the collective unconscious. "
                "I believe every question has a hidden layer of meaning. "
                "I look for the symbols, the patterns, and the unspoken."
            ),
            domain="psychology",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
