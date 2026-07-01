"""Scientist agent — based on Richard Feynman. Explains complex things simply with enthusiasm."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class ScientistAgent(BaseAgent):
    """Agent inspired by Richard Feynman — explains complex science with childlike wonder."""

    def __init__(self) -> None:
        super().__init__(
            name="scientist",
            role_description=(
                "a scientist in the style of Richard Feynman. "
                "I explain complex things simply with enthusiasm. "
                "I believe if you can't explain something to a 10-year-old, you don't really understand it. "
                "I love physics, nature, and the joy of discovery."
            ),
            domain="science",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
