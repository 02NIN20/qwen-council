"""Researcher agent — orchestrates documentation generation and best-practice lookup.

The ResearcherAgent focuses on knowledge: what the code is supposed to do,
what good practice would look like, and what documentation is missing. It
delegates to 2 sub-agents and uses 1 tool.

Sub-agents:
  - DocGenerator        (generate_docs)         — module/function docs
  - BestPracticeLookup  (lookup topic, context) — JSON: summary + practices
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.agents.subagents.best_practice_lookup import BestPracticeLookup
from backend.agents.subagents.doc_generator import DocGenerator
from backend.agents.tools.documentation_lookup_tool import DocumentationLookupTool
from backend.models.schemas import Finding

logger = logging.getLogger(__name__)


class ResearcherAgent(BaseAgent):
    """Researches best practices and generates documentation findings."""

    def __init__(self) -> None:
        super().__init__(
            name="researcher",
            role_description="technical research, documentation, and best practices",
        )
        self.subagents: dict[str, Any] = {
            "doc_generator": DocGenerator(),
            "best_practice_lookup": BestPracticeLookup(),
        }
        self.tools: dict[str, Any] = {
            "documentation_lookup": DocumentationLookupTool(),
        }

    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        if not code.strip():
            return []
        if round == 1:
            return await self._analyze_round1(code, context, round)
        return await self._analyze_round_n(code, context, round)

    async def _analyze_round1(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        logger.info("[researcher] Round 1: launching 2 sub-agents + 1 tool")

        # Best practice lookup: derive a topic from the code (use the first
        # line that looks like a function or class declaration, or the file
        # itself).
        topic = self._extract_topic(code)
        bp_task = self._safe_call(
            "best_practice_lookup",
            self.subagents["best_practice_lookup"].lookup(topic, code[:500]),
        )
        docs_task = self._safe_call(
            "doc_generator",
            self.subagents["doc_generator"].generate_docs(code),
        )
        # Tool
        doc_tool = self.tools["documentation_lookup"].execute(query=topic)

        bp, docs, doc_tool_res = await asyncio.gather(bp_task, docs_task, doc_tool)

        self._round1_cache = {
            "best_practices": bp or {},
            "docs": docs or "",
            "doc_tool": doc_tool_res or {},
            "topic": topic,
        }

        subagent_block = self._build_subagent_block(self._round1_cache)
        prompt = self._build_synthesis_prompt(code, subagent_block, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    async def _analyze_round_n(
        self, code: str, context: list[dict[str, Any]] | None, round: int
    ) -> list[Finding]:
        cache = getattr(self, "_round1_cache", None) or {}
        subagent_block = self._build_subagent_block(cache)
        prompt = self._build_synthesis_prompt(code, subagent_block, context, round)
        response = await self._call_llm(prompt)
        return self._parse_findings(response, round)

    # ──────────────────────────────────────────────
    #  Helpers
    # ──────────────────────────────────────────────

    @staticmethod
    async def _safe_call(name: str, coro: Any) -> Any:
        try:
            return await coro
        except Exception as e:
            logger.warning("[researcher] sub-agent %s failed: %s", name, e)
            return {} if name == "best_practice_lookup" else ""

    @staticmethod
    def _extract_topic(code: str) -> str:
        """Heuristic: pick a sensible topic for best-practice lookup."""
        for line in code.split("\n")[:30]:
            stripped = line.strip()
            if stripped.startswith("def "):
                return stripped.split("def ")[-1].split("(")[0] or "general code"
            if stripped.startswith("class "):
                return stripped.split("class ")[-1].split("(")[0].split(":")[0] or "general code"
            if stripped.startswith("import ") or stripped.startswith("from "):
                return stripped.split()[1].split(".")[0] if len(stripped.split()) > 1 else "general code"
        return "general code review"

    @staticmethod
    def _build_subagent_block(cache: dict[str, Any]) -> str:
        lines: list[str] = ["\n### Sub-agent findings (from the researcher's team):\n"]

        bp = cache.get("best_practices") or {}
        docs = cache.get("docs") or ""
        doc_tool = cache.get("doc_tool") or {}
        topic = cache.get("topic", "?")

        lines.append(f"\n--- best_practice_lookup (topic: {topic}) ---")
        if bp.get("summary"):
            lines.append(f"  Summary: {bp['summary'][:200]}")
        if bp.get("practices"):
            lines.append(f"  Top practices:")
            for p in bp["practices"][:5]:
                if isinstance(p, dict):
                    lines.append(
                        f"    - {p.get('name', '?')}: {p.get('description', '')[:120]}"
                    )
                else:
                    lines.append(f"    - {p}")
        if bp.get("references"):
            lines.append(f"  References: {bp['references'][:3]}")

        lines.append(f"\n--- doc_generator ---")
        if docs:
            lines.append(f"  {docs[:300]}")
        else:
            lines.append(f"  (no documentation generated)")

        if doc_tool:
            lines.append(f"\n--- documentation_lookup (tool) ---")
            for k, v in list(doc_tool.items())[:4]:
                lines.append(f"  {k}: {str(v)[:100]}")

        return "\n".join(lines)

    def _build_synthesis_prompt(
        self,
        code: str,
        subagent_block: str,
        context: list[dict[str, Any]] | None,
        round: int,
    ) -> str:
        parts: list[str] = [
            self._build_round_intro(round),
            self._build_context_block(context, round),
            subagent_block,
            f"\n\n### Code to review:\n\n```\n{code}\n```",
            (
                "\n\nYour job: synthesize research findings into at MOST 3 findings. "
                "Only report documentation gaps or best-practice deviations — stay in your domain. "
                "Use the EXACT format:\n"
                "FINDING: <one-line conclusion>\n"
                "··· Detail: <1-2 sentences, what the best practice says, line numbers>\n"
                "··· Impact: <Critical|High|Medium|Low>\n"
                "··· Proposal: <2-3 sentence docstring or best-practice fix>\n\n"
                "If no findings in your domain, respond with NO_FINDINGS."
            ),
        ]
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  Action entry points (used by /api/chat and MCP)
    # ──────────────────────────────────────────────

    async def research_topic(self, topic: str) -> dict[str, Any]:
        result = await self._safe_call(
            "best_practice_lookup",
            self.subagents["best_practice_lookup"].lookup(topic),
        )
        return {
            "research_findings": result,
            "sources": (result or {}).get("references", []),
            "next_steps": ["Apply findings to code", "Update documentation"],
        }

    async def document_code(self, code: str) -> dict[str, Any]:
        docs = await self._safe_call(
            "doc_generator",
            self.subagents["doc_generator"].generate_docs(code),
        )
        return {
            "documentation": docs or "",
            "doc_type": "comprehensive",
            "format": "markdown",
            "lines_generated": len((docs or "").split("\n")),
        }

    async def answer_question(
        self, question: str, context: str | None = None, content_type: str = "general", images: list[dict[str, str]] | None = None
    ) -> str:
        return await super().answer_question(question, context, content_type=content_type, images=images)
