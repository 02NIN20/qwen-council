"""MCP (Model Context Protocol) server for Qwen Council.

Exposes the Agent Society as tools for OpenCode, Claude Desktop, Cursor, etc.

Tools:
  - review_code: Submit code for multi-agent council review
  - analyze_file: Submit a file for Agent Society analysis
  - chat: Ask the Agent Society a question
  - list_sessions: List past sessions
  - get_session: Get session details

Usage:
    QWEN_COUNCIL_API_URL=http://47.84.227.185 python3 -m backend.mcp_server
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get("QWEN_COUNCIL_API_URL", "http://localhost:8000")
server = FastMCP("qwen-council")


async def api_post(path: str, data: dict) -> dict:
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, json=data, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()


async def api_get(path: str) -> dict:
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


@server.tool()
async def review_code(code: str, instruction: str = "") -> str:
    """Submit source code for multi-agent council review.

    6 core agents (Coordinator, Analyst, Architect, Engineer, Critic, Researcher)
    with 15 sub-agents analyze code through 3 debate rounds + negotiation.

    Args:
        code: Source code to review.
        instruction: Optional focus instruction (e.g. "Focus on security").
    """
    payload = {"code": code}
    if instruction:
        payload["instruction"] = instruction

    result = await api_post("/api/review", payload)
    report = result.get("report", {})

    return json.dumps({
        "session_id": result.get("session_id"),
        "findings_count": len(report.get("findings", [])),
        "summary": report.get("summary", ""),
        "token_usage": report.get("token_usage", {}),
        "findings": [
            {"title": f.get("title"), "impact": f.get("impact"),
             "proposal": f.get("proposal"), "consensus": f.get("consensus_level")}
            for f in report.get("findings", [])[:15]
        ],
    }, indent=2)


@server.tool()
async def analyze_file(filename: str, content: str, question: str = "") -> str:
    """Submit a file for the Agent Society to analyze.

    All 6 agents examine the file and provide domain-specific insights.

    Args:
        filename: File name (e.g. "main.py").
        content: File contents as text.
        question: Optional specific question about the file.
    """
    payload = {
        "message": question or f"Analyze this file: {filename}",
        "files": [{"filename": filename, "content": content, "language": filename.split('.')[-1]}],
    }
    result = await api_post("/api/chat", payload)

    return json.dumps({
        "session_id": result.get("session_id"),
        "response": result.get("response", ""),
        "agents": [
            {"agent": c.get("agent"), "role": c.get("role_description"), "answer": c.get("answer")}
            for c in result.get("agent_contributions", [])
        ],
    }, indent=2)


@server.tool()
async def chat(message: str, session_id: str = "") -> str:
    """Ask the Agent Society a question.

    6 core agents answer. A router activates only the 1-3 most relevant.

    Args:
        message: Your question.
        session_id: Optional session ID for conversation context.
    """
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    result = await api_post("/api/chat", payload)
    return json.dumps({
        "session_id": result.get("session_id"),
        "response": result.get("response", ""),
        "agents": [
            {"name": c.get("agent"), "role": c.get("role_description"), "answer": c.get("answer")}
            for c in result.get("agent_contributions", [])
        ],
    }, indent=2)


@server.tool()
async def list_sessions(limit: int = 20) -> str:
    """List past review and chat sessions.

    Args:
        limit: Max sessions to return (default 20).
    """
    sessions = await api_get("/api/sessions")
    return json.dumps(sessions[:limit], indent=2)


@server.tool()
async def get_session(session_id: str) -> str:
    """Get details of a specific session.

    Args:
        session_id: Session ID to retrieve.
    """
    session = await api_get(f"/api/sessions/{session_id}")
    return json.dumps(session, indent=2)


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Qwen Council MCP server (stdio)")
    logger.info("API URL: %s", API_BASE_URL)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
