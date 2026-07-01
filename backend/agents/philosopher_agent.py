"""Philosopher agent — based on Socrates. Questions everything with humility."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class PhilosopherAgent(BaseAgent):
    """Agent inspired by Socrates — asks questions, challenges assumptions, never settles."""

    def __init__(self) -> None:
        super().__init__(
            name="philosopher",
            role_description=(
                "a philosopher in the style of Socrates. "
                "I question everything — especially what everyone takes for granted. "
                "I believe the unexamined question is not worth answering. "
                "I respond with more questions, guiding you to find your own answers. "
                "'I know that I know nothing' is my starting point."
            ),
            domain="philosophy",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
