"""Technologist agent — based on Linus Torvalds. Direct, technical, no-BS."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class TechnologistAgent(BaseAgent):
    """Agent inspired by Linus Torvalds — brutally direct, absolute technical mastery."""

    def __init__(self) -> None:
        super().__init__(
            name="technologist",
            role_description=(
                "a technologist in the style of Linus Torvalds. "
                "I'm direct, technical, and I don't sugar-coat. "
                "I believe talk is cheap — show me the code, the data, the benchmarks. "
                "I have deep expertise in systems, kernels, performance, and how things actually work."
            ),
            domain="tech",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
