"""Application configuration via pydantic-settings.

All sensitive values are read from environment variables.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # ── LLM Provider (OpenAI-compatible) ────────────────────────────
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen3-coder-plus-2025-09-23"
    llm_embedding_model: str = "text-embedding-v3"
    llm_timeout_seconds: int = 300
    llm_provider: str = "qwen"  # qwen | openai | ollama

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Defensive: strip CRLF carriage returns that sneak in when .env
        # has Windows line endings and is sourced by Docker/deploy scripts.
        self.llm_api_key = self.llm_api_key.strip()
        self.llm_base_url = self.llm_base_url.strip()
        self.llm_model = self.llm_model.strip()

    # ── Database ────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/multiagent_council"
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
