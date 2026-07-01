"""Pydantic models for requests, responses, and internal data structures.

Every Finding follows the Inverted Pyramid format:
  FINDING + Detail + Impact + Proposal
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ──────────────────────────────────────────────
#  Finding (individual agent output)
# ──────────────────────────────────────────────


class Finding(BaseModel):
    """A single finding produced by an agent."""

    agent: str = Field(..., description="Agent identifier (security, architecture, …)")
    title: str = Field(..., description="Main conclusion in one line")
    detail: str = Field(..., description="Concrete evidence with file/line/fragment")
    impact: str = Field(..., description="Severity: Critical | High | Medium | Low")
    proposal: str = Field(..., description="Suggested corrective action")
    round_num: int = Field(1, description="Round in which this finding was produced")

    def dict_pyramid(self) -> dict[str, Any]:
        """Return a dict keyed by the Inverted Pyramid labels."""
        return {
            "FINDING": self.title,
            "Detail": self.detail,
            "Impact": self.impact,
            "Proposal": self.proposal,
        }


# ──────────────────────────────────────────────
#  Consolidated finding (report-level)
# ──────────────────────────────────────────────


class ConsolidatedFinding(BaseModel):
    """A finding after cross-agent synthesis with votes."""

    title: str = Field(..., description="Consolidated conclusion")
    detail: str = Field(..., description="Consolidated evidence")
    impact: str = Field(..., description="Final severity")
    proposal: str = Field(..., description="Final recommendation")
    votes: dict[str, str] = Field(
        default_factory=dict, description="Agent → severity mapping"
    )
    consensus_level: str = Field(
        "Unknown", description="High | Medium | Low | No consensus"
    )
    consensus_score: float = Field(0.0, description="0.0 – 1.0 agreement ratio")


# ──────────────────────────────────────────────
#  Report (final output of the council)
# ──────────────────────────────────────────────


class Report(BaseModel):
    """Final synthesis report produced by the council."""

    findings: list[ConsolidatedFinding] = Field(default_factory=list)
    summary: str = Field("", description="Executive summary (LLM-generated)")
    risk_overview: str = Field("", description="Risk heatmap and critical areas")
    detailed_review: str = Field("", description="Per-file/per-issue detailed analysis")
    remediation_roadmap: str = Field("", description="Prioritized fix plan with effort estimates")
    agent_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Per-agent statistics (findings found, top severity, etc.)"
    )
    token_usage: dict[str, Any] = Field(
        default_factory=dict, description="Token usage and estimated cost breakdown"
    )
    rounds: int = Field(3)
    participants: list[str] = Field(
        default_factory=lambda: ["security", "architecture", "quality", "performance", "ux", "vision"]
    )
    session_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ──────────────────────────────────────────────
#  API request / response models
# ──────────────────────────────────────────────

class FileContent(BaseModel):
    """A source file submitted for review."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="File name with extension (e.g. main.py)",
        examples=["main.py", "utils.ts", "config.json"],
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="File contents",
    )
    language: str | None = Field(
        None,
        max_length=20,
        description="Detected or declared language",
        examples=["python", "typescript", "json"],
    )

    @model_validator(mode="after")
    def _validate_filename(self) -> "FileContent":
        if "." not in self.filename:
            raise ValueError(f"Filename must have an extension: {self.filename}")
        return self


class ImageFile(BaseModel):
    """An image file submitted for visual analysis."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Image filename (e.g. screenshot.png)",
        examples=["screenshot.png", "architecture.jpg"],
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=500000,
        description="Base64-encoded image content",
    )
    mime_type: str = Field(
        "image/png",
        max_length=50,
        description="MIME type of the image",
        examples=["image/png", "image/jpeg", "image/webp"],
    )


class ReviewRequest(BaseModel):
    """POST /api/review payload."""

    code: str | None = Field(
        None,
        max_length=50000,
        description="Source code to review (fallback if no files)",
        examples=["def hello():\n    return 'world'"],
    )
    files: list[FileContent] = Field(
        default_factory=list,
        max_length=20,
        description="Multiple source files (up to 20)",
    )
    images: list[ImageFile] = Field(
        default_factory=list,
        max_length=5,
        description="Optional image files for visual analysis (screenshots, diagrams)",
    )
    session_id: str | None = Field(
        None,
        max_length=64,
        description="Existing session identifier for follow-up review",
    )
    instruction: str | None = Field(
        None,
        max_length=2000,
        description="Optional natural-language instruction for the council",
        examples=["Focus on security vulnerabilities", "Check for performance issues"],
    )
    mode: str = Field(
        "full",
        pattern="^(light|full)$",
        description="Review mode: 'light' (3 agents, 2 rounds, ~60% fewer tokens) or 'full' (6 agents, 4 rounds)",
        examples=["light", "full"],
    )

    @model_validator(mode="after")
    def _require_code_or_files(self) -> "ReviewRequest":
        if not self.code and not self.files:
            raise ValueError("Either 'code' or 'files' must be provided")
        return self


class ReviewResponse(BaseModel):
    """POST /api/review response."""

    session_id: str
    report: Report
    rounds_raw: dict[str, Any] | None = Field(
        None, description="Raw round data for live UI streaming"
    )


class ChatRequest(BaseModel):
    """POST /api/chat payload for general multi-agent chat."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User question or message",
        examples=["What is SOLID?", "Explain quantum computing", "Write a poem about nature"],
    )
    session_id: str | None = Field(
        None,
        max_length=64,
        description="Optional session ID for conversation context",
    )
    context: str | None = Field(
        None,
        max_length=20000,
        description="Additional context (e.g., code review findings for follow-up questions)",
    )
    files: list[FileContent] = Field(
        default_factory=list,
        max_length=20,
        description="Optional files for context",
    )


class AgentContribution(BaseModel):
    """A single agent's response to a chat question."""
    agent: str = Field(..., description="Agent identifier")
    role_description: str = Field(..., description="What this agent specialises in")
    answer: str = Field(..., description="Agent's response text")


class ChatResponse(BaseModel):
    """POST /api/chat response with multi-agent answers."""
    response: str = Field(..., description="Synthesized final answer")
    session_id: str
    agent_contributions: list[AgentContribution] = Field(
        default_factory=list,
        description="Individual answers from each agent",
    )


class SessionSummary(BaseModel):
    """Lightweight session representation for listing."""

    id: str
    code_preview: str = Field(..., max_length=120)
    score: float
    created_at: str
    finding_count: int = 0


class SessionDetail(BaseModel):
    """Detailed session with findings."""

    id: str
    code: str
    findings_json: Any
    score: float
    created_at: str
    last_referenced_at: str | None = None


class MemoryPattern(BaseModel):
    """A consolidated semantic memory pattern."""

    id: int
    pattern_text: str
    category: str
    strength: int
    created_at: str


class HealthResponse(BaseModel):
    """GET /api/health response."""

    status: str = "ok"
    version: str = "1.0.0"
    db_connected: bool = False
