"""LLM Provider Interface for the FFC Framework.

This module provides a flexible interface for different LLM providers with:
- Provider configuration management
- Model selection and validation
- Token tracking and management
- Rate limiting and cost controls
"""

from __future__ import annotations

import abc
import asyncio
import enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TypeVar

from ..core.telemetry import TelemetryManager

T = TypeVar("T")


class ModelType(enum.Enum):
    """Supported model types."""

    COMPLETION = "completion"
    CHAT = "chat"
    EMBEDDING = "embedding"


@dataclass
class TokenUsage:
    """Track token usage for a request."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @property
    def cost(self) -> float:
        """Calculate cost based on token usage."""
        return 0.0  # Subclasses should implement actual cost calculation


@dataclass
class RateLimit:
    """Rate limit configuration."""

    requests_per_minute: int
    tokens_per_minute: int
    concurrent_requests: int

    # Runtime tracking
    request_timestamps: list[datetime] = field(default_factory=list)
    token_usage_window: list[tuple[datetime, int]] = field(default_factory=list)
    current_requests: int = field(default=0)

    def can_make_request(self, token_estimate: int) -> bool:
        """Check if a request can be made within rate limits."""
        now = datetime.now()
        window_start = now - timedelta(minutes=1)

        # Clean up old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps if ts > window_start
        ]
        self.token_usage_window = [
            (ts, tokens) for ts, tokens in self.token_usage_window if ts > window_start
        ]

        # Check limits
        if len(self.request_timestamps) >= self.requests_per_minute:
            return False

        current_tokens = sum(tokens for _, tokens in self.token_usage_window)
        if current_tokens + token_estimate > self.tokens_per_minute:
            return False

        if self.current_requests >= self.concurrent_requests:
            return False

        return True

    def record_request(self, token_count: int) -> None:
        """Record a completed request."""
        now = datetime.now()
        self.request_timestamps.append(now)
        self.token_usage_window.append((now, token_count))
        self.current_requests += 1

    async def complete_request(self) -> bool:
        """Mark a request as completed.

        Returns:
            True to indicate success
        """
        if self.current_requests > 0:
            self.current_requests -= 1
        return True


@dataclass
class ProviderConfig:
    """Base configuration for LLM providers."""

    api_key: str
    organization_id: str | None = None
    default_model: str | None = None
    rate_limit: RateLimit | None = None
    timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 1.5


class LLMProvider(abc.ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self, config: ProviderConfig, telemetry: TelemetryManager | None = None
    ):
        """Initialize provider with configuration.

        Args:
            config: Provider configuration
            telemetry: Optional telemetry manager
        """
        self.config = config
        self.telemetry = telemetry
        self._semaphore = asyncio.Semaphore(
            config.rate_limit.concurrent_requests if config.rate_limit else 10
        )

    @abc.abstractmethod
    async def validate_model(self, model: str) -> bool:
        """Validate if a model is supported and available.

        Args:
            model: Model identifier to validate

        Returns:
            True if model is valid and available
        """
        ...

    @abc.abstractmethod
    def get_token_count(self, text: str) -> int:
        """Get token count for text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        ...

    async def get_token_count_async(self, text: str) -> int:
        """Get token count for text asynchronously.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.get_token_count, text)

    @abc.abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        stop: list[str] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Generate completion for prompt.

        Args:
            prompt: Input prompt
            model: Optional model override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop: Optional stop sequences

        Returns:
            Tuple of (completion text, token usage)
        """
        ...

    @abc.abstractmethod
    async def generate_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        stop: list[str] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Generate chat completion for messages.

        Args:
            messages: List of chat messages
            model: Optional model override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stop: Optional stop sequences

        Returns:
            Tuple of (completion text, token usage)
        """
        ...

    @abc.abstractmethod
    async def generate_embeddings(
        self, texts: list[str], *, model: str | None = None
    ) -> tuple[list[list[float]], TokenUsage]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Optional model override

        Returns:
            Tuple of (list of embeddings, token usage)
        """
        ...

    async def _check_rate_limit(self, token_estimate: int) -> None:
        """Check rate limit and wait if necessary."""
        if not self.config.rate_limit:
            return

        if not self.config.rate_limit.can_make_request(token_estimate):
            raise Exception("Rate limit exceeded")

        self.config.rate_limit.record_request(token_estimate)

    def _record_telemetry(
        self,
        operation: str,
        model: str,
        token_usage: TokenUsage,
        duration: timedelta,
        error: Exception | None = None,
    ) -> None:
        """Record telemetry for LLM operation."""
        if not self.telemetry:
            return

        metadata = {
            "operation": operation,
            "model": model,
            "prompt_tokens": token_usage.prompt_tokens,
            "completion_tokens": token_usage.completion_tokens,
            "total_tokens": token_usage.total_tokens,
            "duration_ms": duration.total_seconds() * 1000,
            "cost": token_usage.cost,
        }

        if error:
            metadata["error"] = str(error)
            metadata["error_type"] = error.__class__.__name__

        self.telemetry.record_metric("llm_request", metadata)
