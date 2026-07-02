"""Application configuration via pydantic-settings.

All sensitive values are read from environment variables.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # ── Qwen Cloud API ──────────────────────────────────────────────
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    qwen_embedding_model: str = "text-embedding-v3"
    qwen_timeout_seconds: int = 300

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Defensive: strip CRLF carriage returns that sneak in when .env
        # has Windows line endings and is sourced by Docker/deploy scripts.
        self.qwen_api_key = self.qwen_api_key.strip()
        self.qwen_base_url = self.qwen_base_url.strip()
        self.qwen_model = self.qwen_model.strip()

    # ── Database ────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/qwen_council"
    database_echo: bool = False

    # ── Redis (optional) ────────────────────────────────────────────
    redis_url: str = ""

    # ── Server ──────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]

    # ── Memory ──────────────────────────────────────────────────────
    episodic_decay_per_day: float = 0.1
    episodic_recovery_on_reference: float = 0.3
    episodic_archive_threshold: float = 0.3
    episodic_max_active: int = 20
    consolidation_threshold: int = 3
    semantic_injection_threshold: float = 0.5

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
