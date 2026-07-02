"""MCP (Model Context Protocol) server for Qwen Council.

Exposes the Agent Society as tools for OpenCode, Claude Desktop, Cursor, etc.

Tools:
  - chat: Quick questions for the Agent Society
  - analyze_file: Analyze a code/text file
  - review_code: Multi-agent code review (3 rounds of debate)
  - generate_code: Generate code from a specification
  - implement_fix: Fix code issues
  - list_sessions: List past sessions
  - get_session: Get session details

Usage:
    QWEN_COUNCIL_API_URL=http://localhost:8000 python3 -m backend.mcp_server
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get("QWEN_COUNCIL_API_URL", "http://localhost:8000")
server = FastMCP("qwen-council")


# ── API helpers ──────────────────────────────────────────────────


async def api_post(path: str, data: dict, timeout: int = 300) -> dict:
    """Make a POST request to the Qwen Council API."""
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=data, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()


async def api_get(path: str) -> dict:
    """Make a GET request to the Qwen Council API."""
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def _call_llm(system: str, prompt: str, max_tokens: int = 2048) -> str:
    """Direct LLM call (no agent routing). Used by generate_code and analyze_file."""
    from openai import AsyncOpenAI
    from backend.config import settings
    client = AsyncOpenAI(api_key=settings.qwen_api_key, base_url=settings.qwen_base_url)
    response = await client.chat.completions.create(
        model=settings.qwen_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


# ── Tools ────────────────────────────────────────────────────────


@server.tool()
async def chat(message: str, session_id: str = "") -> str:
    """Ask a question to the Agent Society (6 role-based AI agents).

    The question is classified and routed to 1-3 relevant agents
    (Analyst, Architect, Engineer, Critic, Researcher, or Coordinator).
    Their answers are merged into a single flowing response.

    Ideal for: design advice, architecture questions, brainstorming,
    code reviews, technical explanations.

    Args:
        message: Your question or request for the agents.
        session_id: Optional session ID to continue a previous conversation.
    """
    try:
        payload: dict[str, Any] = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        result = await api_post("/api/chat", payload, timeout=120)
        return json.dumps({
            "response": result.get("response", ""),
            "session_id": result.get("session_id"),
            "agents": [{"name": c.get("agent"), "answer": c.get("answer")}
                       for c in result.get("agent_contributions", [])],
        }, indent=2)
    except httpx.TimeoutException:
        return json.dumps({"error": "Request timed out. Try a simpler question.", "tool": "chat"})
    except Exception as e:
        logger.exception("chat failed")
        return json.dumps({"error": str(e)[:200], "tool": "chat"})


@server.tool()
async def analyze_file(filename: str, content: str, question: str = "") -> str:
    """Analyze a source code or text file and get insights.

    The file is analyzed by the LLM directly (not routed through agents).
    Best for: understanding unfamiliar code, finding bugs, getting
    suggestions for improvement, reviewing configuration files.

    For files > 4000 chars, only the beginning is analyzed.
    For full code review, use review_code() instead.

    Args:
        filename: File name with extension (e.g. "main.py", "config.json").
        content: Full text content of the file.
        question: Optional specific question (e.g. "Are there security issues?").
    """
    try:
        if len(content) > 50000:
            return json.dumps({"error": "File too large (max 50000 chars)", "filename": filename}, indent=2)

        truncated = content[:4000]
        prompt = (
            f"Analyze this file: {filename}\n"
            f"Question: {question or 'What does this code do?'}\n\n"
            f"```\n{truncated}\n```\n"
            + ("(file truncated to first 4000 chars)\n" if len(content) > 4000 else "")
            + "\nProvide: overview, key components, potential issues, improvement suggestions."
        )
        result = await _call_llm(
            "You are a senior code analyst. Be concise but thorough.",
            prompt,
            max_tokens=2048,
        )
        return json.dumps({
            "filename": filename,
            "analysis": result,
            "truncated": len(content) > 4000,
        }, indent=2)
    except Exception as e:
        logger.exception("analyze_file failed")
        return json.dumps({"error": str(e)[:200], "tool": "analyze_file", "filename": filename})


@server.tool()
async def review_code(code: str, instruction: str = "", mode: str = "light") -> str:
    """Run a full multi-agent code review with 6 specialized agents.

    The code is analyzed through structured debate rounds:
    - light mode: 3 agents, 2 rounds (faster, ~60s)
    - full mode: 6 agents, 4 rounds + negotiation (thorough, ~180s)

    Each agent produces findings in Inverted Pyramid format.
    The council returns: findings with severity, consensus scores,
    and a remediation roadmap.

    Best for: security audits, architecture review, quality checks,
    pre-PR code review, identifying bugs and anti-patterns.

    Args:
        code: The complete source code to review.
        instruction: Optional focus area (e.g. "Focus on security and SQL injection").
        mode: "light" for speed (default), "full" for thoroughness.
    """
    try:
        payload: dict[str, Any] = {"code": code, "mode": mode}
        if instruction:
            payload["instruction"] = instruction
        timeout = 120 if mode == "light" else 300
        result = await api_post("/api/review", payload, timeout=timeout)
        report = result.get("report", {})
        return json.dumps({
            "session_id": result.get("session_id"),
            "findings_count": len(report.get("findings", [])),
            "summary": report.get("summary", ""),
            "token_usage": report.get("token_usage", {}),
            "findings": [{"title": f.get("title"), "impact": f.get("impact"),
                          "proposal": f.get("proposal")}
                         for f in report.get("findings", [])[:20]],
        }, indent=2)
    except httpx.TimeoutException:
        return json.dumps({"error": "Review timed out. Try mode='light' or smaller code.", "tool": "review_code"})
    except Exception as e:
        logger.exception("review_code failed")
        return json.dumps({"error": str(e)[:200], "tool": "review_code"})


@server.tool()
async def generate_code(specification: str, language: str = "python") -> str:
    """Generate production-ready code from a specification.

    Uses Qwen LLM directly to write clean, well-commented code
    following best practices for the specified language.

    Best for: boilerplate generation, API endpoints, data models,
    utility functions, configuration files, test cases.

    Args:
        specification: What to build (e.g. "FastAPI CRUD for users with SQLite").
        language: Target programming language (python, javascript, typescript, go, rust, etc.).
    """
    try:
        prompt = (
            f"Generate complete {language} code:\n{specification}\n\n"
            f"Requirements:\n- Well-structured, production-ready code\n"
            f"- Comments explaining key sections\n- Error handling\n"
            f"- Best practices for {language}"
        )
        result = await _call_llm(
            f"You are an expert {language} developer. Write clean code with comments.",
            prompt,
            max_tokens=4096,
        )
        return json.dumps({
            "language": language,
            "specification": specification,
            "code": result,
        }, indent=2)
    except Exception as e:
        logger.exception("generate_code failed")
        return json.dumps({"error": str(e)[:200], "tool": "generate_code"})


@server.tool()
async def implement_fix(code: str, issue: str) -> str:
    """Fix a bug or code issue and explain the solution.

    Analyzes the problematic code and produces a corrected version
    with explanation of what was wrong and why the fix works.

    Best for: fixing bugs, patching security vulnerabilities,
    resolving performance bottlenecks, correcting logic errors.

    Args:
        code: The current code containing the issue.
        issue: Description of what's wrong (e.g. "SQL injection in line 12").
    """
    try:
        prompt = (
            f"Fix this issue:\nIssue: {issue}\n\n"
            f"Code:\n```\n{code}\n```\n\n"
            f"Output the corrected code with brief explanation of what changed."
        )
        result = await _call_llm(
            "You are an expert developer. Fix the issue and explain your changes concisely.",
            prompt,
            max_tokens=4096,
        )
        return json.dumps({"issue": issue, "fix": result}, indent=2)
    except Exception as e:
        logger.exception("implement_fix failed")
        return json.dumps({"error": str(e)[:200], "tool": "implement_fix"})


@server.tool()
async def list_sessions(limit: int = 20) -> str:
    """List past code review and chat sessions.

    Returns a list of session summaries with IDs, dates, and finding counts.

    Args:
        limit: Maximum number of sessions to return (default 20, max 100).
    """
    try:
        sessions = await api_get("/api/sessions")
        return json.dumps([
            {"id": s.get("id"), "date": s.get("created_at"),
             "findings": s.get("finding_count", 0), "score": s.get("score", 0)}
            for s in sessions[:min(limit, 100)]
        ], indent=2)
    except Exception as e:
        logger.exception("list_sessions failed")
        return json.dumps({"error": str(e)[:200], "tool": "list_sessions"})


@server.tool()
async def get_session(session_id: str) -> str:
    """Get details of a specific session by ID.

    Returns the full session data including reviewed code,
    findings or chat history, and metadata.

    Args:
        session_id: Session ID to retrieve (e.g. "ses-abc123").
    """
    try:
        session = await api_get(f"/api/sessions/{session_id}")
        return json.dumps(session, indent=2, default=str)
    except Exception as e:
        logger.exception("get_session failed")
        return json.dumps({"error": str(e)[:200], "tool": "get_session"})


# ── Main ─────────────────────────────────────────────────────────


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Qwen Council MCP server starting (stdio)")
    logger.info("API URL: %s", API_BASE_URL)
    try:
        server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
