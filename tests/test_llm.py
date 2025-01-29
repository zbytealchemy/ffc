"""Tests for LLM Integration System."""

import asyncio
import json

import pytest
from ffc.llm.prompts import (
    PromptManager,
    PromptTemplate,
    ResponseSchema,
    SimpleRenderer,
)
from ffc.llm.providers import LLMProvider, ProviderConfig, RateLimit, TokenUsage


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, config: ProviderConfig | None = None) -> None:
        super().__init__(config or ProviderConfig(api_key="mock-api-key"))

    async def get_token_count(self, text: str) -> int:
        # Simple mock: 1 token per word
        return len(text.split())

    async def validate_model(self, model: str) -> bool:
        # Mock validation
        return model in {"gpt-3.5-turbo", "gpt-4"}

    async def generate_completion(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        stop: list[str] | None = None,
    ) -> tuple[str, TokenUsage]:
        # Check rate limit
        token_estimate = await self.get_token_count(prompt)
        await self._check_rate_limit(token_estimate)

        await asyncio.sleep(0.1)  # Simulate API call
        response = f"Completion for: {prompt}"
        usage = TokenUsage(
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(response.split()),
            total_tokens=len(prompt.split()) + len(response.split()),
        )

        if self.config.rate_limit:
            await self.config.rate_limit.complete_request()

        return response, usage

    async def generate_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        stop: list[str] | None = None,
    ) -> tuple[str, TokenUsage]:
        await asyncio.sleep(0.1)  # Simulate API call

        # Check rate limit
        token_estimate = 0
        for m in messages:
            token_estimate += await self.get_token_count(m["content"])
        await self._check_rate_limit(token_estimate)

        last_message = messages[-1]["content"]
        response = f"Chat response to: {last_message}"
        usage = TokenUsage(
            prompt_tokens=sum(len(m["content"].split()) for m in messages),
            completion_tokens=len(response.split()),
            total_tokens=sum(len(m["content"].split()) for m in messages)
            + len(response.split()),
        )

        if self.config.rate_limit:
            await self.config.rate_limit.complete_request()

        return response, usage

    async def generate_embeddings(
        self, texts: list[str], *, model: str | None = None
    ) -> tuple[list[list[float]], TokenUsage]:
        """Generate embeddings for texts."""
        # Check rate limit
        token_estimate: int = sum(
            await asyncio.gather(*(self.get_token_count(text) for text in texts))
        )
        await self._check_rate_limit(token_estimate)

        await asyncio.sleep(0.1)  # Simulate API call
        embeddings = [[0.1, 0.2, 0.3] for _ in texts]  # Mock embeddings
        usage = TokenUsage(
            prompt_tokens=token_estimate,
            completion_tokens=0,
            total_tokens=token_estimate,
        )

        if self.config.rate_limit:
            await self.config.rate_limit.complete_request()

        return embeddings, usage


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting functionality."""
    rate_limit = RateLimit(
        requests_per_minute=2, tokens_per_minute=100, concurrent_requests=1
    )

    config = ProviderConfig(api_key="test", rate_limit=rate_limit)
    provider = MockLLMProvider(config)  # Update provider config with rate limit

    # First request should succeed
    response1, usage1 = await provider.generate_completion("Test prompt 1")
    assert "Test prompt 1" in response1

    # Second request should succeed
    response2, usage2 = await provider.generate_completion("Test prompt 2")
    assert "Test prompt 2" in response2

    # Third request should be rate limited
    with pytest.raises(Exception, match="Request rate limit exceeded"):
        await provider.generate_completion("Test prompt 3")


@pytest.mark.asyncio
async def test_prompt_template_rendering():
    """Test prompt template rendering."""
    template = PromptTemplate(
        name="test", template="Hello ${name}! Here are your ${item_type}: ${items}"
    )

    renderer = SimpleRenderer()
    manager = PromptManager(renderer=renderer)
    manager.add_template(template)

    variables = {
        "name": "User",
        "item_type": "fruits",
        "items": '["apple", "banana", "orange"]',
    }

    result = manager.render("test", variables)
    assert "Hello User!" in result
    assert "apple" in result
    assert "banana" in result
    assert "orange" in result


def test_response_schema_validation():
    """Test response schema validation."""
    schema = ResponseSchema(
        format="json",
        required_fields={"name", "age"},
        schema={
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        },
    )

    # Valid response
    valid_response = json.dumps({"name": "Test User", "age": 25})
    is_valid, error = schema.validate(valid_response)
    assert is_valid
    assert error is None

    # Invalid response (missing field)
    invalid_response = json.dumps({"name": "Test User"})
    is_valid, error = schema.validate(invalid_response)
    assert not is_valid
    assert "Missing required fields" in error


@pytest.mark.asyncio
async def test_token_usage_tracking():
    """Test token usage tracking."""
    config = ProviderConfig(
        api_key="test",
        rate_limit=RateLimit(
            requests_per_minute=10, tokens_per_minute=1000, concurrent_requests=2
        ),
    )
    provider = MockLLMProvider(config)

    # Generate multiple completions
    prompts = [
        "Short prompt",
        "Medium length prompt with more words",
        "Very long prompt with many more words to test token counting",
    ]

    usages = []
    for prompt in prompts:
        _, usage = await provider.generate_completion(prompt)
        usages.append(usage)

    # Verify token counts increase with prompt length
    assert usages[0].prompt_tokens < usages[1].prompt_tokens
    assert usages[1].prompt_tokens < usages[2].prompt_tokens
