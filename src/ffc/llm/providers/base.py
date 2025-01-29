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

from ...core.telemetry import TelemetryManager

T = TypeVar("T")


class ModelType(str, enum.Enum):
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

    def cost(self) -> float:
        """Calculate cost based on token usage."""
        # TODO: Implement cost calculation based on model pricing
        return 0.0


@dataclass
class RateLimit:
    """Rate limit configuration."""

    requests_per_minute: int
    tokens_per_minute: int
    concurrent_requests: int
    request_timestamps: list[datetime] = field(default_factory=list)
    token_usage_window: list[tuple[datetime, int]] = field(default_factory=list)
    current_requests: int = field(default=0)

    def can_make_request(self, token_estimate: int) -> bool:
        """Check if a request can be made within rate limits.

        Args:
            token_estimate: Estimated tokens for request

        Returns:
            True if request can be made

        Raises:
            Exception: If rate limit is exceeded
        """
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Clean old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps if ts > minute_ago
        ]
        self.token_usage_window = [
            (ts, tokens) for ts, tokens in self.token_usage_window if ts > minute_ago
        ]

        # Check limits
        if len(self.request_timestamps) >= self.requests_per_minute:
            raise Exception("Request rate limit exceeded")

        total_tokens = sum(tokens for _, tokens in self.token_usage_window)
        if total_tokens + token_estimate > self.tokens_per_minute:
            raise Exception("Token rate limit exceeded")

        if self.current_requests >= self.concurrent_requests:
            raise Exception("Concurrent request limit exceeded")

        return True

    async def check_rate_limit(self, token_estimate: int) -> bool:
        """Async alias for can_make_request."""
        return self.can_make_request(token_estimate)

    def record_request(self, token_count: int) -> None:
        """Record a completed request.

        Args:
            token_count: Number of tokens used
        """
        now = datetime.now()
        self.request_timestamps.append(now)
        self.token_usage_window.append((now, token_count))
        self.current_requests += 1

    async def complete_request(self) -> None:
        """Mark a request as completed."""
        self.current_requests = max(0, self.current_requests - 1)


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
        pass

    @abc.abstractmethod
    async def get_token_count(self, text: str) -> int:
        """Get token count for text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        pass

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
        pass

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
        pass

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
        pass

    async def _check_rate_limit(self, token_estimate: int) -> None:
        """Check rate limit and wait if necessary.

        Args:
            token_estimate: Estimated tokens for request

        Raises:
            Exception: If rate limit is exceeded
        """
        if not self.config.rate_limit:
            return

        # Try a few times with short waits
        for _ in range(3):
            try:
                if self.config.rate_limit.can_make_request(token_estimate):
                    self.config.rate_limit.record_request(token_estimate)
                    return
            except Exception as e:
                # On last attempt, re-raise the exception
                if _ == 2:
                    raise e
                await asyncio.sleep(0.1)

        raise Exception("Rate limit exceeded after retries")

    def _record_telemetry(
        self,
        operation: str,
        model: str,
        token_usage: TokenUsage,
        duration: timedelta,
        error: Exception | None = None,
    ) -> None:
        """Record telemetry for LLM operation.

        Args:
            operation: Operation name (completion, chat, embedding)
            model: Model used
            token_usage: Token usage stats
            duration: Operation duration
            error: Optional error that occurred
        """
        if not self.telemetry:
            return

        self.telemetry.record_llm_operation(
            provider=self.__class__.__name__,
            operation=operation,
            model=model,
            token_usage=token_usage,
            duration=duration,
            error=error,
        )
