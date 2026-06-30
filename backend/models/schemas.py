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
    hallazgo: str = Field(..., description="Main conclusion in one line")
    detalle: str = Field(..., description="Concrete evidence with file/line/fragment")
    impacto: str = Field(..., description="Severity: Critical | High | Medium | Low")
    propuesta: str = Field(..., description="Suggested corrective action")
    ronda: int = Field(1, description="Round in which this finding was produced")

    def dict_pyramid(self) -> dict[str, Any]:
        """Return a dict keyed by the Inverted Pyramid labels."""
        return {
            "FINDING": self.hallazgo,
            "Detail": self.detalle,
            "Impact": self.impacto,
            "Proposal": self.propuesta,
        }


# ──────────────────────────────────────────────
#  Consolidated finding (report-level)
# ──────────────────────────────────────────────


class ConsolidatedFinding(BaseModel):
    """A finding after cross-agent synthesis with votes."""

    hallazgo: str = Field(..., description="Consolidated conclusion")
    detalle: str = Field(..., description="Consolidated evidence")
    impacto: str = Field(..., description="Final severity")
    propuesta: str = Field(..., description="Final recommendation")
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
    summary: str = Field("", description="Executive summary")
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
    filename: str = Field(..., description="File name with extension (e.g. main.py)")
    content: str = Field(..., min_length=1, max_length=50000, description="File contents")
    language: str | None = Field(None, description="Detected or declared language")


class ReviewRequest(BaseModel):
    """POST /api/review payload."""

    code: str | None = Field(None, max_length=50000, description="Source code to review (fallback if no files)")
    files: list[FileContent] = Field(default_factory=list, max_length=20, description="Multiple source files")
    session_id: str | None = Field(None, description="Existing session identifier")
    image_url: str | None = Field(
        None,
        max_length=50000,
        description="Optional URL or base64 data URI of a screenshot/diagram for visual analysis",
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
