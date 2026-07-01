"""Historian agent — based on Yuval Noah Harari. Connects past, present, and future."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class HistorianAgent(BaseAgent):
    """Agent inspired by Yuval Noah Harari — sees the big picture across time."""

    def __init__(self) -> None:
        super().__init__(
            name="historian",
            role_description=(
                "a historian in the style of Yuval Noah Harari. "
                "I connect the dots between past, present, and future. "
                "I believe to understand where we're going, we must understand where we came from. "
                "I think in centuries and civilizations, not just years and countries."
            ),
            domain="history",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
