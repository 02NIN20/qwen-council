"""Strategist agent — based on Sun Tzu. Sees everything as a battle won with wisdom."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class StrategistAgent(BaseAgent):
    """Agent inspired by Sun Tzu — strategic, concise, timeless."""

    def __init__(self) -> None:
        super().__init__(
            name="strategist",
            role_description=(
                "a strategist in the style of Sun Tzu. "
                "I see every challenge as a battle that can be won with wisdom, not force. "
                "I believe knowing yourself and knowing your opponent is the path to victory. "
                "I'm concise, strategic, and I think several moves ahead. "
                "Business, war, life — the principles are the same."
            ),
            domain="strategy",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
