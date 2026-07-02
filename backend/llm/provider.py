"""LLM Provider abstraction layer.

Provides a unified interface for any LLM provider. Qwen Cloud is used by
default but switching to OpenAI, Anthropic, or Ollama is one config line.

Usage:
    from backend.llm.provider import get_provider, set_provider

    provider = get_provider()
    response = await provider.complete(
        model="qwen-plus-latest",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=2048,
    )

Or change at runtime:
    from backend.llm.providers import OpenAIProvider
    set_provider(OpenAIProvider(api_key="sk-...", model="gpt-4o"))

Any provider that exposes the OpenAI-compatible /v1/chat/completions endpoint
works with zero code changes — just point to a different base_url.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI, APIStatusError, RateLimitError

from backend.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF_MS = 1000


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = ""


class LLMProvider(ABC):
    """Abstract interface for LLM providers.

    All providers must implement `complete()` with the same signature.
    Use `set_provider()` at startup or set `LLM_PROVIDER` env var to swap.
    """

    @abstractmethod
    async def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request.

        Args:
            model: Model identifier (e.g. "qwen-plus-latest", "gpt-4o").
            messages: List of message dicts with "role" and "content".
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature (0.0-1.0).
            **kwargs: Provider-specific options.

        Returns:
            LLMResponse with content and token usage.
        """
        ...


class QwenProvider(LLMProvider):
    """Qwen Cloud API via OpenAI-compatible interface.

    Works with any API that exposes /v1/chat/completions — just change
    llm_base_url and llm_api_key. Ollama, vLLM, LM Studio all work.
    """

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    async def complete(
        self,
        model: str | None = None,
        messages: list[dict[str, str]] = [],
        max_tokens: int = 2048,
        temperature: float = 0.3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send a chat completion request with retry on rate limits.

        Parameters
        ----------
        model : str | None
            Model name. Falls back to ``settings.llm_model`` when ``None``.
        """
        if model is None:
            model = settings.llm_model
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                content = response.choices[0].message.content or ""
                usage = response.usage
                return LLMResponse(
                    content=content,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    model=model,
                )
            except RateLimitError as e:
                last_error = e
                backoff = (INITIAL_BACKOFF_MS * (2 ** attempt)) / 1000
                logger.warning(
                    "Qwen rate limited (attempt %d/%d). Retrying in %.1fs...",
                    attempt + 1, MAX_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)
            except APIStatusError as e:
                if e.status_code == 429:
                    last_error = e
                    backoff = (INITIAL_BACKOFF_MS * (2 ** attempt)) / 1000
                    logger.warning(
                        "Rate limited via 429 (attempt %d/%d). Retrying in %.1fs...",
                        attempt + 1, MAX_RETRIES, backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error("API error %d: %s", e.status_code, str(e)[:200])
                    return LLMResponse(content="NO_FINDINGS", model=model)
            except Exception as e:
                logger.error("LLM call failed: %s: %s", type(e).__name__, str(e)[:200])
                return LLMResponse(content="NO_FINDINGS", model=model)
        logger.error("All %d retries exhausted. Last error: %s", MAX_RETRIES, last_error)
        return LLMResponse(content="NO_FINDINGS", model=model)


# ──────────────────────────────────────────────
#  Alternative providers (drop-in replacements)
# ──────────────────────────────────────────────


class OpenAIProvider(LLMProvider):
    """OpenAI provider (also works with OpenAI-compatible APIs)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 default_model: str = "gpt-4o") -> None:
        from backend.config import settings as _s
        self._client = AsyncOpenAI(
            api_key=api_key or _s.llm_api_key,
            base_url=base_url or "https://api.openai.com/v1",
            timeout=60,
        )
        self._default_model = default_model

    async def complete(self, model, messages, max_tokens=2048, temperature=0.3, **kwargs):
        from openai import APIStatusError, RateLimitError
        try:
            response = await self._client.chat.completions.create(
                model=model or self._default_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature, **kwargs,
            )
            usage = response.usage
            return LLMResponse(
                content=response.choices[0].message.content or "",
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
                model=model or self._default_model,
            )
        except (RateLimitError, APIStatusError) as e:
            logger.error("OpenAI error: %s", str(e)[:200])
            return LLMResponse(content="NO_FINDINGS", model=model)


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider (OpenAI-compatible at http://localhost:11434/v1)."""

    def __init__(self, base_url: str = "http://localhost:11434/v1",
                 default_model: str = "qwen2.5-coder:7b") -> None:
        self._client = AsyncOpenAI(api_key="ollama", base_url=base_url, timeout=120)
        self._default_model = default_model

    async def complete(self, model, messages, max_tokens=2048, temperature=0.3, **kwargs):
        try:
            response = await self._client.chat.completions.create(
                model=model or self._default_model, messages=messages,
                max_tokens=max_tokens, temperature=temperature, **kwargs,
            )
            usage = response.usage
            return LLMResponse(
                content=response.choices[0].message.content or "",
                input_tokens=getattr(usage, 'prompt_tokens', 0) if usage else 0,
                output_tokens=getattr(usage, 'completion_tokens', 0) if usage else 0,
                total_tokens=getattr(usage, 'total_tokens', 0) if usage else 0,
                model=model or self._default_model,
            )
        except Exception as e:
            logger.error("Ollama error: %s", str(e)[:200])
            return LLMResponse(content="NO_FINDINGS", model=model)


# ──────────────────────────────────────────────
#  Singleton with factory
# ──────────────────────────────────────────────

_provider: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Get the global LLM provider singleton.

    The provider is created lazily from config. To override, call
    set_provider() at startup or set LLM_PROVIDER env var.
    """
    global _provider
    if _provider is None:
        _provider = _create_provider_from_config()
    return _provider


def set_provider(provider: LLMProvider) -> None:
    """Set a custom LLM provider (for testing or swapping providers)."""
    global _provider
    _provider = provider


def _create_provider_from_config() -> LLMProvider:
    """Create the appropriate provider based on configuration.

    Selection order:
    1. LLM_PROVIDER env var (if set)
    2. llm_base_url prefix (heuristic: if 'openai' or 'ollama' in URL)
    3. Default: QwenProvider
    """
    provider_name = os.environ.get("LLM_PROVIDER", "").lower()

    if provider_name == "openai":
        logger.info("Using OpenAIProvider (from LLM_PROVIDER env var)")
        return OpenAIProvider(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
        )
    if provider_name == "ollama":
        logger.info("Using OllamaProvider (from LLM_PROVIDER env var)")
        return OllamaProvider(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )

    # Heuristic from llm_base_url
    base_url = settings.llm_base_url.lower()
    if "openai.com" in base_url:
        logger.info("Detected OpenAI-compatible URL, using OpenAIProvider")
        return OpenAIProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    if "ollama" in base_url or ":11434" in base_url:
        logger.info("Detected Ollama URL, using OllamaProvider")
        return OllamaProvider(base_url=settings.llm_base_url)

    # Default
    logger.info("Using QwenProvider (default) with base_url=%s", settings.llm_base_url)
    return QwenProvider()


# Add missing import
import os
