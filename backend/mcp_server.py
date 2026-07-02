"""MCP (Model Context Protocol) server for Qwen Council.

Exposes the Agent Society as tools that any MCP-compatible client
(Claude Desktop, Cursor, OpenCode, etc.) can invoke.

Tools:
  - review_code: Submit code for multi-agent council review
  - analyze_file: Submit a file for agent analysis (chat mode)
  - chat: Ask the Agent Society a question
  - list_sessions: List past review/chat sessions
  - get_session: Get details of a specific session

Usage:
    python -m backend.mcp_server  # stdio mode (for Claude Desktop, Cursor, OpenCode)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

API_BASE_URL = os.environ.get("QWEN_COUNCIL_API_URL", "http://localhost:8000")

server = Server("qwen-council")


async def _api_post(path: str, data: dict) -> dict:
    """Make a POST request to the Qwen Council API."""
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(url, json=data, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()


async def _api_get(path: str) -> dict:
    """Make a GET request to the Qwen Council API."""
    url = f"{API_BASE_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


@server.tool()
async def review_code(code: str, instruction: str = "") -> list[TextContent]:
    """Submit source code for multi-agent council review.

    Six core agents (Coordinator, Analyst, Architect, Engineer, Critic, Researcher)
    with 15 sub-agents analyze the code through 3 debate rounds + negotiation.

    Args:
        code: The source code to review.
        instruction: Optional review instruction (e.g. "Focus on security").

    Returns:
        JSON string with findings, summary, token usage, and estimated cost.
    """
    payload = {"code": code}
    if instruction:
        payload["instruction"] = instruction

    result = await _api_post("/api/review", payload)
    report = result.get("report", {})

    output = {
        "session_id": result.get("session_id"),
        "findings_count": len(report.get("findings", [])),
        "summary": report.get("summary", ""),
        "token_usage": report.get("token_usage", {}),
        "findings": [
            {
                "title": f.get("title"),
                "impact": f.get("impact"),
                "proposal": f.get("proposal"),
                "consensus": f.get("consensus_level"),
                "votes": f.get("votes"),
            }
            for f in report.get("findings", [])[:10]
        ],
    }
    return [TextContent(type="text", text=json.dumps(output, indent=2))]


@server.tool()
async def analyze_file(filename: str, content: str, question: str = "") -> list[TextContent]:
    """Submit a file for the Agent Society to analyze.

    All 6 core agents examine the file and provide insights from their
    respective domains (analysis, architecture, engineering, critique, research).

    Args:
        filename: Name of the file (e.g. "main.py").
        content: File contents as text.
        question: Optional specific question about the file.

    Returns:
        JSON string with synthesized analysis from all agents.
    """
    payload = {
        "message": question or f"Analyze this file: {filename}",
        "files": [{"filename": filename, "content": content, "language": filename.split('.')[-1]}],
    }

    result = await _api_post("/api/chat", payload)

    output = {
        "session_id": result.get("session_id"),
        "response": result.get("response", ""),
        "agent_contributions": [
            {"agent": c.get("agent"), "role": c.get("role_description"), "answer": c.get("answer")}
            for c in result.get("agent_contributions", [])
        ],
    }
    return [TextContent(type="text", text=json.dumps(output, indent=2))]


@server.tool()
async def chat(message: str, session_id: str = "") -> list[TextContent]:
    """Ask the Agent Society a question.

    Six core agents (Coordinator, Analyst, Architect, Engineer, Critic, Researcher)
    answer any question. A router activates only the 1-3 most relevant agents.

    Args:
        message: The question to ask.
        session_id: Optional session ID for conversation context.

    Returns:
        JSON string with the synthesized answer and agent contributions.
    """
    payload = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    result = await _api_post("/api/chat", payload)

    output = {
        "session_id": result.get("session_id"),
        "response": result.get("response", ""),
        "agents": [
            {"name": c.get("agent"), "role": c.get("role_description"), "answer": c.get("answer")}
            for c in result.get("agent_contributions", [])
        ],
    }
    return [TextContent(type="text", text=json.dumps(output, indent=2))]


@server.tool()
async def list_sessions(limit: int = 20) -> list[TextContent]:
    """List past review and chat sessions.

    Args:
        limit: Maximum number of sessions to return (default 20).

    Returns:
        JSON array of session summaries.
    """
    sessions = await _api_get("/api/sessions")
    return [TextContent(type="text", text=json.dumps(sessions[:limit], indent=2))]


@server.tool()
async def get_session(session_id: str) -> list[TextContent]:
    """Get details of a specific session including findings or chat history.

    Args:
        session_id: The session ID to retrieve.

    Returns:
        JSON object with session details.
    """
    session = await _api_get(f"/api/sessions/{session_id}")
    return [TextContent(type="text", text=json.dumps(session, indent=2))]


async def amain() -> None:
    """Run the MCP server in stdio mode."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Qwen Council MCP server")
    logger.info("API URL: %s", API_BASE_URL)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
