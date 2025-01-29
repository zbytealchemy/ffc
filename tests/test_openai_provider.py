"""Tests for OpenAI provider."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ffc.llm.providers.base import ProviderConfig
from ffc.llm.providers.openai import OpenAIProvider
from openai.types.chat import ChatCompletion
from openai.types.completion import Completion
from openai.types.embedding import Embedding


@pytest.fixture
def provider():
    """Create a provider instance."""
    config = ProviderConfig(
        api_key="test",
        organization_id="test",
        timeout=60,
        max_retries=3,
        rate_limit=None,
    )
    return OpenAIProvider(config=config)


@pytest.fixture
def mock_encoder():
    """Create a mock tiktoken encoder."""
    with patch("tiktoken.encoding_for_model") as mock:
        encoder = AsyncMock()
        encoder.encode = MagicMock(return_value=[1, 2, 3])  # Non-async encode method
        mock.return_value = encoder
        yield encoder


@pytest.fixture
def mock_client(provider):
    """Create a mock OpenAI client."""
    with patch("openai.AsyncClient") as mock:
        client = AsyncMock()

        # Mock completions
        completions = AsyncMock()
        completions.create = AsyncMock(
            return_value=Completion(
                id="test",
                choices=[
                    {"text": "test completion", "index": 0, "finish_reason": "stop"}
                ],
                created=1234567890,
                model="gpt-3.5-turbo-instruct",
                object="text_completion",
                usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            )
        )
        client.completions = completions

        # Mock chat completions
        chat = AsyncMock()
        completions = AsyncMock()
        completions.create = AsyncMock(
            return_value=ChatCompletion(
                id="test",
                choices=[
                    {
                        "message": {
                            "role": "assistant",
                            "content": "test chat completion",
                        },
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ],
                created=1234567890,
                model="gpt-3.5-turbo",
                object="chat.completion",
                usage={"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6},
            )
        )
        chat.completions = completions
        client.chat = chat

        # Mock embeddings
        embeddings = AsyncMock()
        embeddings.create = AsyncMock(
            return_value=type(
                "EmbeddingResponse",
                (),
                {
                    "data": [
                        Embedding(
                            embedding=[0.1, 0.2, 0.3], index=0, object="embedding"
                        ),
                        Embedding(
                            embedding=[0.4, 0.5, 0.6], index=1, object="embedding"
                        ),
                    ],
                    "model": "text-embedding-ada-002",
                    "object": "list",
                    "usage": type("Usage", (), {"prompt_tokens": 6, "total_tokens": 6}),
                },
            )()
        )
        client.embeddings = embeddings

        # Mock the client directly
        mock.return_value = client

        # Mock the provider's client
        provider.client = client

        yield client


@pytest.mark.asyncio
async def test_validate_model(provider):
    """Test model validation."""
    assert await provider.validate_model("gpt-3.5-turbo")
    assert await provider.validate_model("gpt-4")
    assert not await provider.validate_model("invalid-model")


@pytest.mark.asyncio
async def test_get_token_count(provider, mock_encoder):
    """Test token counting."""
    text = "test text"
    count = await provider.get_token_count(text)
    assert count == 3  # Length of mock encoder output
    mock_encoder.encode.assert_called_once_with(text)


@pytest.mark.asyncio
async def test_generate_completion(provider, mock_client):
    """Test completion generation."""
    prompt = "test prompt"
    completion, usage = await provider.generate_completion(prompt)
    assert completion == "test completion"
    assert usage.prompt_tokens == 3
    assert usage.completion_tokens == 2
    assert usage.total_tokens == 5
    mock_client.completions.create.assert_awaited_once_with(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        temperature=1.0,
        max_tokens=None,
        stop=None,
    )


@pytest.mark.asyncio
async def test_generate_chat_completion(provider, mock_client):
    """Test chat completion generation."""
    messages = [{"role": "user", "content": "test message"}]
    completion, usage = await provider.generate_chat_completion(messages)
    assert completion == "test chat completion"
    assert usage.prompt_tokens == 3
    assert usage.completion_tokens == 3
    assert usage.total_tokens == 6
    mock_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=1.0,
        max_tokens=None,
        stop=None,
    )


@pytest.mark.asyncio
async def test_generate_embeddings(provider, mock_client):
    """Test embedding generation."""
    texts = ["test text 1", "test text 2"]
    embeddings, usage = await provider.generate_embeddings(texts)
    assert len(embeddings) == 2
    assert embeddings[0] == [0.1, 0.2, 0.3]
    assert embeddings[1] == [0.4, 0.5, 0.6]
    assert usage.prompt_tokens == 6
    assert usage.total_tokens == 6
    mock_client.embeddings.create.assert_awaited_once_with(
        model="text-embedding-ada-002", input=texts
    )


@pytest.mark.asyncio
async def test_rate_limit(provider, mock_client):
    """Test rate limiting."""
    provider.config.rate_limit = AsyncMock()
    provider.config.rate_limit.check_rate_limit = AsyncMock()
    provider.config.rate_limit.complete_request = AsyncMock()

    await provider.generate_completion("test prompt")

    provider.config.rate_limit.check_rate_limit.assert_awaited_once()
    provider.config.rate_limit.complete_request.assert_called_once()
