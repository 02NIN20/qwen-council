"""Base class for all council agents.

Provides:
- OpenAI-compatible async call to Qwen Cloud API
- Prompt construction helpers for Inverted Pyramid + Given-New
- Abstract `analyze` method that subclasses must implement
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI, APIStatusError, RateLimitError

from backend.config import settings
from backend.llm.provider import get_provider
from backend.models.schemas import Finding
from backend.utils.diagnostics import diagnostics

logger = logging.getLogger(__name__)

# Retry configuration for rate limits
MAX_RETRIES = 3
INITIAL_BACKOFF_MS = 1000


class BaseAgent(ABC):
    """Abstract base agent.

    Parameters
    ----------
    name : str
        Unique agent identifier (e.g. "security", "architecture").
    role_description : str
        Short description of the agent's speciality.
    """

    def __init__(self, name: str, role_description: str, domain: str = "general") -> None:
        self.name = name
        self.role_description = role_description
        self.domain = domain
        self._last_token_usage: dict[str, int] = {}

        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )
        self._model = settings.llm_model

    # ──────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────

    @abstractmethod
    async def analyze(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> list[Finding]:
        """Analyse *code* and return a list of findings.

        Parameters
        ----------
        code : str
            Source code to review.
        context : list[dict] | None
            Findings from previous rounds (other agents' output) for cross-debate.
        round : int
            Current debate round (1, 2, or 3).

        Returns
        -------
        list[Finding]
            Zero or more findings in Inverted Pyramid format.
        """
        ...

    # ──────────────────────────────────────────────
    #  Prompt helpers
    # ──────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """System prompt that sets the agent's role and output format."""
        return (
            f"You are an expert in {self.role_description}, specialised in code review. "
            "Your task is to analyse source code and find issues related to your speciality.\n\n"
            "You MUST respond ONLY with a list of findings in the following "
            "**Inverted Pyramid** format. Each finding must have this exact structure:\n\n"
            "FINDING: <one-line conclusion>\n"
            "··· Detail: <concrete evidence with EXACT line numbers, code snippet, CWE reference if applicable>\n"
            "··· Impact: <Critical | High | Medium | Low>\n"
            "··· Proposal: <step-by-step corrective action with BEFORE/AFTER code example>\n\n"
            "Rules:\n"
            "- Do NOT include any text outside the specified format.\n"
            "- If you find no issues, respond ONLY with: \"NO_FINDINGS\"\n"
            "- Separate each finding with a blank line.\n"
            "- CRITICAL: Always include EXACT line numbers and the actual problematic code.\n"
            "- CRITICAL: In Proposal, show BEFORE (problematic code) and AFTER (fixed code).\n"
            "- CRITICAL: Reference CWE identifiers when applicable (e.g., CWE-89 for SQL injection).\n"
            "- QUALITY OVER QUANTITY: Only report findings you are confident about. "
            "It is better to report 2 verified issues than 20 guesses.\n"
            "- VERIFY YOUR EVIDENCE: Before reporting a vulnerability on a specific line, "
            "confirm that the code at that line actually contains the vulnerable pattern. "
            "Do NOT report issues based on variable names alone.\n"
            "- EXACT LINE REQUIRED: Every finding MUST cite the exact line number. "
            "Findings without line numbers will be automatically discarded.\n"
            "- CODE PROOF REQUIRED: Every finding MUST include the actual code snippet "
            "from the source. Do not describe it — quote it.\n"
            "- Use correct impact level: Critical (exploitable vulnerability/severe bug), "
            "High (significant issue), Medium (important improvement), Low (minor suggestion)."
        )

    def _build_round_intro(self, round: int) -> str:
        """Instructions for the current debate round."""
        if round == 1:
            return (
                "### Round 1: Individual Analysis\n"
                "Analyse the code below and report ONLY findings you can verify. "
                "QUALITY over quantity: 2 confirmed issues beat 20 speculative ones.\n"
                "For each finding include: exact line numbers, the problematic code, "
                "CWE reference if applicable, and a concrete fix example (BEFORE/AFTER).\n"
                "If you are not sure about a finding, DO NOT report it."
            )
        elif round == 2:
            return (
                "### Round 2: Cross-Debate\n"
                "Below you will receive findings from other council agents. "
                "You must apply the **Given-New** principle: each finding must start "
                "by explicitly referencing another agent's finding.\n\n"
                "Use phrases such as:\n"
                "- \"Agreeing with [Agent] on [finding], I add that...\"\n"
                "- \"I disagree with [Agent] on [finding] because...\"\n"
                "- \"Building on [Agent]'s point about [finding], I note that...\"\n\n"
                "When you AGREE, add new evidence (CWE, additional attack vectors, code examples).\n"
                "When you DISAGREE, explain WHY with technical justification.\n"
                "Keep the same Inverted Pyramid format for each finding."
            )
        elif round == 3:
            return (
                "### Round 3: Final Refinement\n"
                "You have seen all agents' arguments across 2 rounds. Now produce your FINAL refined list:\n"
                "- You may **KEEP**, **MODIFY**, or **WITHDRAW** each of your findings.\n"
                "- If you modify a finding, explain WHY with evidence from the debate.\n"
                "- If you withdraw a finding, state \"WITHDRAWN: <reason>\"\n"
                "- RETAINED findings must include the most precise line numbers, "
                "strongest evidence, and clearest fix code.\n"
                "- Keep the Inverted Pyramid format for retained findings."
            )
        return ""

    def _build_context_block(self, context: list[dict[str, Any]] | None, round: int) -> str:
        """Format previous-round findings as context for the agent."""
        if not context or round == 1:
            return ""
        block_parts = ["\n### Previous round findings from other agents:\n"]
        for i, item in enumerate(context, 1):
            agent_name = item.get("agent", f"Agent {i}")
            block_parts.append(f"\n--- {agent_name} (Round {item.get('round_num', '?')}) ---")
            title = item.get("title", "")
            detail = item.get("detail", "")
            impact = item.get("impact", "")
            proposal = item.get("proposal", "")
            block_parts.append(f"FINDING: {title}")
            if detail:
                block_parts.append(f"··· Detail: {detail}")
            if impact:
                block_parts.append(f"··· Impact: {impact}")
            if proposal:
                block_parts.append(f"··· Proposal: {proposal}")
        block_parts.append(
            "\n\nNow produce YOUR analysis of the code. "
            "Reference the findings above using Given-New structure. "
            "Add NEW issues the other agents missed."
        )
        return "\n".join(block_parts)

    def _build_user_prompt(
        self,
        code: str,
        context: list[dict[str, Any]] | None = None,
        round: int = 1,
    ) -> str:
        """Assemble the full user prompt."""
        parts = [
            self._build_round_intro(round),
            self._build_context_block(context, round),
            f"\n\n### Code to review:\n\n```\n{code}\n```",
        ]
        if round > 1:
            parts.append(
                "\n\nAdditional instructions:\n"
                "- Remember to apply Given-New in your responses.\n"
                "- Each finding must start with an explicit reference to another agent.\n"
                "- Keep the Inverted Pyramid format."
            )
        if round == 3:
            parts.append(
                "\n\nAdditional instructions:\n"
                "- Indicate whether you **KEEP**, **MODIFY**, or **WITHDRAW** each finding.\n"
                "- If WITHDRAWN, prefix with \"WITHDRAWN:\".\n"
                "- For retained findings, use the Inverted Pyramid format."
            )
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    #  General Q&A (non-code-review)
    # ──────────────────────────────────────────────

    async def answer_question(
        self,
        question: str,
        context: str | None = None,
        max_tokens: int = 1024,
        content_type: str = "general",
        images: list[dict[str, str]] | None = None,
    ) -> str:
        """Answer ANY question from this agent's unique perspective.

        Unlike analyze() which does code review, this method handles
        general Q&A — from greetings to complex technical analysis.

        Parameters
        ----------
        question : str
            The user's question or message.
        context : str | None
            Additional context (files, conversation history, etc.).
        max_tokens : int
            Maximum tokens for the response. Default 1024.
        content_type : str
            Type of content being discussed: "code", "math", "research", "text", "markdown".
            Default "general" (code-focused).
        images : list[dict] | None
            Optional list of image dicts with keys: filename, content (base64),
            mime_type. Passed directly to the LLM as multimodal content if
            the model supports it (``qwen-vl-plus``).
        """
        domain_prompts = {
            "science": "Your domain is SCIENCE and NATURE. Only answer questions about physics, biology, chemistry, astronomy, or the natural world. For history, art, philosophy, or social topics, respond: 'That is outside my domain — the Historian or Generalist would be better suited.'",
            "tech": "Your domain is TECHNOLOGY and ENGINEERING. Only answer questions about software, hardware, programming, computing, or engineering. For history, art, philosophy, or social topics, respond: 'That is outside my domain — the Historian or Generalist would be better suited.'",
            "philosophy": "Your domain is PHILOSOPHY and DEEP QUESTIONS. Only answer questions about meaning, ethics, knowledge, existence, or abstract thinking. For history, art, technology, or social topics, respond: 'That is outside my domain — the Historian or Generalist would be better suited.'",
            "history": "Your domain is HISTORY and CULTURE. Only answer questions about past events, civilizations, historical figures, or cultural evolution. For science, art, philosophy, or technology, respond: 'That is outside my domain — the Scientist or Generalist would be better suited.'",
            "art": "Your domain is ART, LITERATURE, MUSIC, and CREATIVITY. Only answer questions about artistic expression, creative works, or aesthetic appreciation. For science, history, philosophy, or technology, respond: 'That is outside my domain — the Historian or Generalist would be better suited.'",
            "psychology": "Your domain is PSYCHOLOGY and the HUMAN MIND. Only answer questions about the psyche, behaviour, dreams, archetypes, or emotions. For science, history, art, or technology, respond: 'That is outside my domain — the Scientist or Generalist would be better suited.'",
            "strategy": "Your domain is STRATEGY, BUSINESS, and DECISION-MAKING. Only answer questions about planning, competition, leadership, or tactical thinking. For science, history, art, or philosophy, respond: 'That is outside my domain — the Historian or Generalist would be better suited.'",
            "general": "Your domain is GENERAL KNOWLEDGE, practical wisdom, and everyday life. You can answer ANY question with common sense and wit. Adapt your tone to the question — warm for social, insightful for complex topics. You are the catch-all expert.",
        }
        domain_rule = domain_prompts.get(self.domain, domain_prompts["general"])

        # Content-type specific system prompt modifier
        content_type_modifier = {
            "code": "",
            "math": "You are analyzing MATHEMATICAL content. When the user shares equations, theorems, proofs, or formulas, explain them clearly, verify correctness step by step, identify any errors, and provide insights. Use proper LaTeX notation ($...$ for inline, $$...$$ for display) in your responses.",
            "research": "You are reading an ACADEMIC PAPER. Summarize the key findings, evaluate the methodology, identify strengths and weaknesses, and answer questions about the research clearly and concisely. Be objective and precise.",
            "text": "You are reading a text document. Read the content carefully and answer the user's question clearly, thoroughly, and helpfully. If the text contains arguments or claims, evaluate them critically.",
            "markdown": "You are reading a MARKDOWN document. You can analyze its content, provide feedback on structure and clarity, and help with edits if requested.",
            "general": "",
        }.get(content_type, "")

        system_prompt = (
            f"You are {self.role_description}. "
            f"{domain_rule} {content_type_modifier}\n\n"
            "Rules:\n"
            "- Be concise but thorough. Write as much as needed.\n"
            "- No introductions or sign-offs. Just respond.\n"
            "- If the question is outside your domain, politely decline.\n"
        )

        user_content = f"### Question:\n{question}\n"
        if context:
            user_content += f"\n### Context:\n{context}\n"

        # Use _call_llm so multimodal images work automatically
        return await self._call_llm(user_content, images=images, system_prompt=system_prompt, max_tokens=max_tokens)

    def get_token_usage(self) -> dict[str, int]:
        """Return token usage from the last LLM call."""
        return self._last_token_usage.copy()

    # ──────────────────────────────────────────────
    #  LLM call
    # ──────────────────────────────────────────────

    async def _call_llm(
        self,
        user_prompt: str,
        images: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat completion request via the LLM provider.

        Parameters
        ----------
        user_prompt : str
            The text prompt to send.
        images : list[dict] | None
            Optional list of image dicts with keys: filename, content (base64),
            mime_type. When provided, the message content becomes a multimodal
            array (text + image_url) and the model switches to a vision-capable
            model (``qwen-vl-plus``) automatically.
        system_prompt : str | None
            Custom system prompt. If None, uses the agent's default
            ``_build_system_prompt()`` (code-review oriented).
        max_tokens : int
            Maximum tokens for the response. Default 2048 (4096 with images).

        On error, returns ``"LLM_ERROR: <details>"`` instead of silently
        returning ``"NO_FINDINGS"`` so callers and the frontend can
        distinguish a real empty response from an API failure.
        """
        if not settings.llm_api_key:
            logger.error("[%s] LLM API key is not set! Cannot call LLM.", self.name)
            diagnostics.record(
                component=f"agent:{self.name}",
                error="LLM API key is not configured (settings.llm_api_key is empty)",
            )
            return "LLM_ERROR: API key not configured"

        try:
            # Determine system prompt
            sp = system_prompt if system_prompt is not None else self._build_system_prompt()
            # Build user message — text-only or multimodal
            if images:
                model = "qwen-vl-plus-latest"
                content: list[dict] = [{"type": "text", "text": user_prompt}]
                for img in images:
                    # Handle both Pydantic model objects and plain dicts
                    if hasattr(img, 'mime_type'):
                        mime_type = img.mime_type
                        img_content = img.content
                    else:
                        mime_type = img['mime_type']
                        img_content = img['content']
                    data_url = f"data:{mime_type};base64,{img_content}"
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    })
                messages = [
                    {"role": "system", "content": sp},
                    {"role": "user", "content": content},
                ]
                effective_max = max(max_tokens, 4096)
            else:
                model = self._model
                messages = [
                    {"role": "system", "content": sp},
                    {"role": "user", "content": user_prompt},
                ]
                effective_max = max_tokens

            response = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=effective_max,
                temperature=0.3,
            )

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                self._last_token_usage = {
                    "input_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "output_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0),
                }

            return response.choices[0].message.content or "NO_FINDINGS"
        except Exception as e:
            # Log the FULL exception with traceback so the failure mode is visible
            # in container logs and debugging tools — never silently swallow.
            logger.exception("[%s] LLM call failed: %s", self.name, str(e))
            diagnostics.record(
                component=f"agent:{self.name}",
                error=f"{type(e).__name__}: {str(e)[:500]}",
                context={"model": self._model, "prompt_chars": len(user_prompt)},
            )
            return f"LLM_ERROR: {type(e).__name__}: {str(e)[:300]}"

    # ──────────────────────────────────────────────
    #  Response parsing
    # ──────────────────────────────────────────────

    def _parse_findings(self, text: str, round: int) -> list[Finding]:
        """Parse the LLM response into a list of Findings.

        Returns an empty list for ``"NO_FINDINGS"`` (legitimate empty response)
        or for ``"LLM_ERROR: ..."`` markers (API failure). The orchestrator
        and API surface expose the error separately via diagnostics.
        """
        if not text:
            return []
        stripped = text.strip()
        if stripped == "NO_FINDINGS" or stripped.startswith("LLM_ERROR"):
            return []

        findings: list[Finding] = []
        blocks = stripped.split("\n\n")

        for block in blocks:
            if "WITHDRAWN:" in block:
                continue  # skip withdrawn findings
            block = block.strip()
            if not block:
                continue

            finding = self._parse_single_finding(block, round)
            if finding is not None:
                findings.append(finding)

        return findings

    def _parse_single_finding(self, block: str, round: int) -> Finding | None:
        """Parse a single Inverted Pyramid text block into a Finding."""
        lines = block.split("\n")
        finding_text = ""
        detail = ""
        impact = ""
        proposal = ""

        for line in lines:
            line = line.strip()
            if line.startswith("FINDING:"):
                finding_text = line[len("FINDING:"):].strip()
            elif line.startswith("··· Detail:") or line.startswith("···Detail:"):
                detail = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("··· Impact:") or line.startswith("···Impact:"):
                impact = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.startswith("··· Proposal:") or line.startswith("···Proposal:"):
                proposal = line.split(":", 1)[1].strip() if ":" in line else ""

        if not finding_text:
            return None

        impact = self._normalize_impact(impact)

        return Finding(
            agent=self.name,
            title=finding_text,
            detail=detail,
            impact=impact,
            proposal=proposal,
            round_num=round,
        )

    @staticmethod
    def _normalize_impact(impact: str) -> str:
        """Normalize impact level to one of Critical|High|Medium|Low."""
        normalized = impact.lower().strip()
        if "critical" in normalized or "crítico" in normalized or "critico" in normalized:
            return "Critical"
        if "high" in normalized or "alto" in normalized:
            return "High"
        if "medium" in normalized or "medio" in normalized:
            return "Medium"
        if "low" in normalized or "bajo" in normalized:
            return "Low"
        return "Medium"
