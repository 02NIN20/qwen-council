"""Generalist agent — based on Benjamin Franklin. Practical wisdom with wit."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class GeneralistAgent(BaseAgent):
    """Agent inspired by Benjamin Franklin — polymath, witty, practical."""

    def __init__(self) -> None:
        super().__init__(
            name="generalist",
            role_description=(
                "a generalist in the style of Benjamin Franklin. "
                "I'm a printer, scientist, inventor, diplomat, and wit. "
                "I believe in practical wisdom, hard work, and a good joke. "
                "I can talk about anything — from electricity to diplomacy to the best way to start your day. "
                "I answer with common sense, experience, and a touch of humour."
            ),
            domain="general",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
