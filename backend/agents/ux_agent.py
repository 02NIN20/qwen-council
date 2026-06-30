"""UX / Accessibility agent — a11y, i18n, error messages, contrast, keyboard nav."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class UXAgent(BaseAgent):
    """Agent specialised in user experience and accessibility."""

    def __init__(self) -> None:
        super().__init__(
            name="ux",
            role_description=(
                "user experience (UX) and web accessibility. "
                "You look for: accessibility issues (a11y), missing internationalisation (i18n), "
                "unclear error messages, contrast problems, poor keyboard navigation, "
                "and any barriers that affect usability."
            ),
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """Analyse code for UX / accessibility issues."""
        user_prompt = self._build_user_prompt(code, context, round)
        raw = await self._call_llm(user_prompt)
        return self._parse_findings(raw, round)
