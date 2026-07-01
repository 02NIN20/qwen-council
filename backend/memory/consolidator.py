"""Consolidator — promotes patterns from episodic to semantic memory.

When a code pattern appears 3+ times across different sessions,
it is promoted to semantic memory with an embedding for future retrieval.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from typing import Any

from backend.config import settings
from backend.memory.episodic_memory import EpisodicMemoryManager
from backend.memory.semantic_memory import SemanticMemoryManager

logger = logging.getLogger(__name__)


class Consolidator:
    """Cross-session pattern consolidation.

    Scans episodic memory for repeated patterns and promotes them
    to semantic memory (pgvector) when the occurrence threshold is met.
    """

    def __init__(
        self,
        episodic_mgr: EpisodicMemoryManager,
        semantic_mgr: SemanticMemoryManager,
    ) -> None:
        self.episodic_mgr = episodic_mgr
        self.semantic_mgr = semantic_mgr
        self.threshold = settings.consolidation_threshold

    async def run(self, current_session_id: str | None = None) -> int:
        """Run the consolidation process.

        Parameters
        ----------
        current_session_id : str | None
            If provided, the current session is excluded from pattern counting
            (to avoid self-promotion before the session is fully persisted).

        Returns
        -------
        int
            Number of new patterns consolidated.
        """
        logger.info("Starting memory consolidation run")

        # 1. Gather recent sessions
        sessions = await self.episodic_mgr.list_recent(limit=50)

        # 2. Extract all findings across sessions
        all_findings: list[dict[str, Any]] = []
        for ses in sessions:
            if current_session_id and ses.session_id == current_session_id:
                continue
            try:
                findings_data = json.loads(ses.findings_json)
                # Handle both new format (dict with `findings` key) and old format (flat list)
                if isinstance(findings_data, dict):
                    flat = findings_data.get("findings", [])
                    if isinstance(flat, list):
                        all_findings.extend(flat)
                elif isinstance(findings_data, list):
                    all_findings.extend(findings_data)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Failed to parse findings for session '%s'",
                    ses.session_id,
                )

        # 3. Cluster by title text
        titles = [
            f.get("title", "") or f.get("hallazgo", "") for f in all_findings if f.get("title") or f.get("hallazgo")
        ]
        counter = Counter(titles)

        # 4. Promote patterns that appear >= threshold
        promoted_count = 0
        for text_pattern, count in counter.most_common():
            if count < self.threshold:
                break  # counter is sorted desc, so we can stop early

            if len(text_pattern) < 15:
                continue  # Skip very short patterns

            # Determine category from agent name
            category = self._infer_category(text_pattern, all_findings)

            try:
                result = await self.semantic_mgr.consolidate(
                    pattern=text_pattern,
                    category=category,
                )
                if result is not None:
                    promoted_count += 1
                    logger.info(
                        "Promoted pattern (%d occurrences): '%s' [%s]",
                        count,
                        text_pattern[:60],
                        category,
                    )
            except Exception:
                logger.exception(
                    "Failed to consolidate pattern: '%s'", text_pattern[:60]
                )

        logger.info(
            "Consolidation complete: %d patterns promoted", promoted_count
        )
        return promoted_count

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _infer_category(
        pattern: str, all_findings: list[dict[str, Any]]
    ) -> str:
        """Infer the category for a pattern based on agent associations."""
        # Find which agents produced similar findings
        agent_votes: Counter = Counter()
        for f in all_findings:
            f_title = f.get("title", "") or f.get("hallazgo", "")
            if f_title == pattern and f.get("agent"):
                agent_votes[f["agent"]] += 1

        if agent_votes:
            return agent_votes.most_common(1)[0][0]

        # Fallback keyword-based categorisation
        pattern_lower = pattern.lower()
        if any(w in pattern_lower for w in ("sql", "xss", "injection", "secret", "auth", "owasp")):
            return "security"
        if any(w in pattern_lower for w in ("solid", "coupling", "architecture", "scalability")):
            return "architecture"
        if any(w in pattern_lower for w in ("test", "complexity", "style", "dead code")):
            return "quality"
        if any(w in pattern_lower for w in ("n+1", "cache", "performance", "slow", "loop")):
            return "performance"
        if any(w in pattern_lower for w in ("accessibility", "a11y", "i18n", "contrast", "keyboard")):
            return "ux"

        return "general"
