"""Architecture agent — SOLID, design patterns, coupling, scalability."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class ArchitectureAgent(BaseAgent):
    """Agent specialised in software architecture."""

    def __init__(self) -> None:
        super().__init__(
            name="architecture",
            role_description=(
                "software architecture and SOLID principles. "
                "You look for: SOLID principle violations, high coupling, "
                "low cohesion, scalability issues, misuse of design patterns, "
                "and lack of separation of concerns."
            ),
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """Analyse code for architecture issues."""
        user_prompt = self._build_user_prompt(code, context, round)
        raw = await self._call_llm(user_prompt)
        return self._parse_findings(raw, round)
