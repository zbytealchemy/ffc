# LLM Integration Guide

This guide covers integrating Large Language Models (LLMs) with the Firefly Catcher Framework.

## Overview

FFC provides a flexible LLM integration system that supports:
- Multiple LLM providers
- Template-based prompt management
- Context handling
- Token management
- Error handling and fallback strategies

## Provider Configuration

### Supported Providers
- OpenAI
- Anthropic
- Custom providers

### Configuration Example
```python
from ffc.llm import LLMConfig, Provider

config = LLMConfig(
    provider=Provider.OPENAI,
    model="gpt-4",
    api_key="your-api-key",
    max_tokens=2000
)
```

## Prompt Management

### Template System
```python
from ffc.llm import PromptTemplate

template = PromptTemplate(
    name="task_decomposition",
    content="Break down the following task into steps: {task}",
    variables=["task"]
)
```

### Context Handling
```python
from ffc.llm import Context

context = Context()
context.add("system_prompt", "You are a helpful AI assistant")
context.add("user_context", user_data)
```

## Error Handling

### Retry Mechanism
```python
from ffc.llm import RetryConfig

retry_config = RetryConfig(
    max_retries=3,
    backoff_factor=1.5,
    errors_to_retry=[RateLimitError, TemporaryError]
)
```

### Fallback Strategy
```python
from ffc.llm import FallbackConfig

fallback_config = FallbackConfig(
    providers=[Provider.OPENAI, Provider.ANTHROPIC],
    models=["gpt-4", "claude-2"]
)
```

## Cost Management

### Token Tracking
```python
from ffc.llm import TokenTracker

tracker = TokenTracker()
tracker.start_session()
# ... LLM operations ...
usage = tracker.get_session_usage()
```

### Budget Control
```python
from ffc.llm import BudgetManager

budget = BudgetManager(
    max_daily_tokens=100000,
    max_cost_usd=10.0
)
```

## Best Practices

1. **Token Efficiency**
   - Use efficient prompts
   - Implement context windowing
   - Clean and preprocess inputs

2. **Error Handling**
   - Always implement retry logic
   - Use fallback providers
   - Log and monitor errors

3. **Cost Control**
   - Set budget limits
   - Monitor token usage
   - Implement cost optimization strategies

4. **Security**
   - Secure API key storage
   - Sanitize inputs
   - Implement rate limiting

## Example Implementation

```python
from ffc.llm import LLMManager, PromptTemplate, Context

# Initialize LLM manager
llm = LLMManager(config)

# Create prompt template
template = PromptTemplate(
    name="analysis",
    content="Analyze the following code: {code}"
)

# Prepare context
context = Context()
context.add("code", source_code)

# Execute LLM call with retry and fallback
result = await llm.generate(
    template=template,
    context=context,
    retry_config=retry_config,
    fallback_config=fallback_config
)
```
