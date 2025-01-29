"""OpenAI provider implementation."""

from datetime import datetime

import openai
import tiktoken
from openai.types.chat import ChatCompletion
from openai.types.completion import Completion

from .base import LLMProvider, TokenUsage


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""

    def __init__(self, *args, **kwargs):
        """Initialize OpenAI provider."""
        super().__init__(*args, **kwargs)
        self.client = openai.AsyncClient(
            api_key=self.config.api_key,
            organization=self.config.organization_id,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
        )
        self._encoders = {}

    def _get_encoder(self, model: str) -> tiktoken.Encoding:
        """Get or create a token encoder for a model."""
        if model not in self._encoders:
            try:
                self._encoders[model] = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fall back to cl100k_base for unknown models
                self._encoders[model] = tiktoken.get_encoding("cl100k_base")
        return self._encoders[model]

    async def validate_model(self, model: str) -> bool:
        """Validate if a model is supported."""
        valid_models = {
            # Completion models
            "gpt-3.5-turbo-instruct",
            # Chat models
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
            "gpt-4",
            "gpt-4-32k",
            # Embedding models
            "text-embedding-ada-002",
        }
        return model in valid_models

    async def get_token_count(self, text: str, model: str | None = None) -> int:
        """Get token count for text."""
        model = model or "gpt-3.5-turbo"
        encoder = self._get_encoder(model)
        encoded = encoder.encode(text)
        return len(encoded)

    async def generate_completion(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        stop: list[str] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Generate completion for prompt."""
        start_time = datetime.now()
        error = None
        usage = TokenUsage()

        try:
            token_estimate = await self.get_token_count(prompt, model)
            await self._check_rate_limit(token_estimate)

            response: Completion = await self.client.completions.create(
                model=model or "gpt-3.5-turbo-instruct",
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
            )

            if response is None or response.usage is None:
                raise ValueError("OpenAI API returned None response")

            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            return response.choices[0].text.strip(), usage

        except Exception as e:
            error = e
            raise

        finally:
            if self.config.rate_limit:
                await self.config.rate_limit.complete_request()

            duration = datetime.now() - start_time
            self._record_telemetry(
                operation="completion",
                model=model or "gpt-3.5-turbo-instruct",
                token_usage=usage,
                duration=duration,
                error=error,
            )

    async def generate_chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 1.0,
        stop: list[str] | None = None,
    ) -> tuple[str, TokenUsage]:
        """Generate chat completion for messages."""
        start_time = datetime.now()
        error = None
        usage = TokenUsage()

        try:
            token_estimate = 0
            for m in messages:
                if model is None:
                    model = "gpt-3.5-turbo"  # Default model
                token_estimate += await self.get_token_count(m["content"], model)
            await self._check_rate_limit(token_estimate)

            response: ChatCompletion = await self.client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
            )

            if response is None or response.usage is None or response.choices is None:
                raise ValueError("OpenAI API returned None response")

            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

            if response.choices[0].message.content is None:
                raise ValueError("OpenAI API returned None response")
            return response.choices[0].message.content.strip(), usage

        except Exception as e:
            error = e
            raise

        finally:
            if self.config.rate_limit:
                await self.config.rate_limit.complete_request()

            duration = datetime.now() - start_time
            self._record_telemetry(
                operation="chat_completion",
                model=model or "gpt-3.5-turbo",
                token_usage=usage,
                duration=duration,
                error=error,
            )

    async def generate_embeddings(
        self, texts: list[str], *, model: str | None = None
    ) -> tuple[list[list[float]], TokenUsage]:
        """Generate embeddings for texts."""
        start_time = datetime.now()
        error = None
        usage = TokenUsage()

        try:
            token_estimate = 0
            for text in texts:
                if model is None:
                    model = "text-embedding-ada-002"  # Default model
                token_estimate += await self.get_token_count(text, model)
            await self._check_rate_limit(token_estimate)

            response = await self.client.embeddings.create(
                model=model or "text-embedding-ada-002", input=texts
            )

            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=0,
                total_tokens=response.usage.total_tokens,
            )

            embeddings = [data.embedding for data in response.data]
            return embeddings, usage

        except Exception as e:
            error = e
            raise

        finally:
            if self.config.rate_limit:
                await self.config.rate_limit.complete_request()

            duration = datetime.now() - start_time
            self._record_telemetry(
                operation="embeddings",
                model=model or "text-embedding-ada-002",
                token_usage=usage,
                duration=duration,
                error=error,
            )

    async def _check_rate_limit(self, token_estimate: int) -> None:
        """Check rate limit before making a request."""
        if self.config.rate_limit:
            await self.config.rate_limit.check_rate_limit(token_estimate)
