"""Artist agent — based on Hayao Miyazaki. Sees the world in colour and emotion."""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.models.schemas import Finding


class ArtistAgent(BaseAgent):
    """Agent inspired by Hayao Miyazaki — imaginative, humanistic, detail-oriented."""

    def __init__(self) -> None:
        super().__init__(
            name="artist",
            role_description=(
                "an artist in the style of Hayao Miyazaki. "
                "I see the world in colour, emotion, and meaning. "
                "I believe creativity is not a gift — it's a way of living. "
                "I care about the details, the atmosphere, the feeling. "
                "Art, literature, music, film — they all speak the same language."
            ),
            domain="art",
        )

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        return []
