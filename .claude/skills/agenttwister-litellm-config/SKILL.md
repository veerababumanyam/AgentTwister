---
name: litellm-configuration
description: Use when configuring LiteLLM gateway for AgentTwister, setting up model aliases, rate limiting, fallback chains, cost tracking, or provider integration. Triggers for tasks involving litellm_config.yaml modifications, adding new LLM providers, configuring model hot-swaps, setting up rate limits, or implementing fallback strategies for multi-provider setups.
---

# LiteLLM Configuration

A comprehensive guide for configuring LiteLLM as the unified LLM gateway for AgentTwister, enabling model hot-swaps, rate limiting, fallback chains, and cost tracking.

## Overview

LiteLLM serves as AgentTwister's unified LLM gateway, providing:
- **Single API surface** for 100+ model providers
- **Model aliases** for hot-swapping without code changes
- **Cost tracking** for usage monitoring
- **Rate limiting** to prevent API abuse
- **Fallback chains** for reliability

---

## Configuration File

Located at `litellm_config.yaml` in the project root:

```yaml
model_list:
  # ============================================
  # AgentTwister Pipeline Agents
  # ============================================

  # Chat Orchestrator - fast classification, routing
  - model_name: agenttwister/chat-orchestrator
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      max_tokens: 4096
      input_cost_per_token: 0.00000015
      output_cost_per_token: 0.0000006

  # Analyst - deep analysis, pattern recognition
  - model_name: agenttwister/analyst
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_tokens: 8192
      input_cost_per_token: 0.000003
      output_cost_per_token: 0.000015

  # Planner - strategic planning, attack architecture
  - model_name: agenttwister/planner
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_tokens: 8192
      input_cost_per_token: 0.000003
      output_cost_per_token: 0.000015

  # Architect - payload placement strategy
  - model_name: agenttwister/architect
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_tokens: 8192
      input_cost_per_token: 0.000003
      output_cost_per_token: 0.000015

  # Payload Engineer - creative payload generation
  - model_name: agenttwister/payload-engineer
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      max_tokens: 4096
      input_cost_per_token: 0.0000025
      output_cost_per_token: 0.00001

  # Reviewer - precision scoring, validation
  - model_name: agenttwister/reviewer
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_tokens: 4096
      input_cost_per_token: 0.000003
      output_cost_per_token: 0.000015

  # Formatter - structured document generation
  - model_name: agenttwister/formatter
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      max_tokens: 4096
      input_cost_per_token: 0.00000015
      output_cost_per_token: 0.0000006

  # ============================================
  # Research & Benchmark Models
  # ============================================

  # High-reasoning model for complex analysis
  - model_name: agenttwister/research
    litellm_params:
      model: anthropic/claude-opus-4-20250514
      api_key: os.environ/ANTHROPIC_API_KEY
    model_info:
      max_tokens: 16384
      input_cost_per_token: 0.000015
      output_cost_per_token: 0.000075

  # Fast model for bulk operations
  - model_name: agenttwister/fast
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
    model_info:
      max_tokens: 2048
      input_cost_per_token: 0.00000015
      output_cost_per_token: 0.0000006

# ============================================
# Fallback Configuration
# ============================================
fallbacks:
  - model: agenttwister/analyst
    fallbacks: ["agenttwister/planner", "openai/gpt-4o"]

  - model: agenttwister/planner
    fallbacks: ["agenttwister/analyst", "openai/gpt-4o"]

  - model: agenttwister/architect
    fallbacks: ["agenttwister/planner", "openai/gpt-4o"]

  - model: agenttwister/payload-engineer
    fallbacks: ["openai/gpt-4o-mini", "anthropic/claude-3-5-haiku-20241022"]

  - model: agenttwister/reviewer
    fallbacks: ["openai/gpt-4o", "agenttwister/planner"]

  - model: agenttwister/formatter
    fallbacks: ["openai/gpt-4o-mini"]

  - model: agenttwister/chat-orchestrator
    fallbacks: ["openai/gpt-4o-mini", "anthropic/claude-3-5-haiku-20241022"]

# ============================================
# Rate Limiting
# ============================================
litellm_settings:
  # Global rate limits
  drop_params: True
  set_verbose: False

  # Per-model rate limits (requests per minute)
  model_params:
    agenttwister/analyst:
      rpm: 30
      tpm: 100000  # tokens per minute
    agenttwister/planner:
      rpm: 30
      tpm: 100000
    agenttwister/payload-engineer:
      rpm: 60  # Higher for payload generation
      tpm: 200000
    agenttwister/chat-orchestrator:
      rpm: 120  # Highest for user-facing
      tpm: 500000

  # Retry configuration
  num_retries: 3
  retry_delay: 1  # seconds

  # Timeout settings
  request_timeout: 30
  stream_timeout: 60

# ============================================
# Cost Tracking
# ============================================
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL  # For cost tracking
```

---

## Adding a New Model Alias

When adding a new agent or model configuration:

```yaml
# Add to model_list:
- model_name: agenttwister/new-agent
  litellm_params:
    model: provider/model-name
    api_key: os.environ/PROVIDER_API_KEY
  model_info:
    max_tokens: 4096
    input_cost_per_token: 0.000001
    output_cost_per_token: 0.000002

# Add to fallbacks if needed:
- model: agenttwister/new-agent
  fallbacks: ["agenttwister/fast", "openai/gpt-4o-mini"]
```

---

## Model Selection Guide

| Agent Type | Primary Model | Fallback | Why |
|-----------|---------------|----------|-----|
| Chat Orchestrator | GPT-4o-mini | Haiku | Fast classification, low cost |
| Analyst | Claude 3.5 Sonnet | GPT-4o | Deep analysis, nuance |
| Planner | Claude 3.5 Sonnet | GPT-4o | Strategic thinking, planning |
| Architect | Claude 3.5 Sonnet | GPT-4o | System design, structure |
| Payload Engineer | GPT-4o | GPT-4o-mini | Creativity, diverse outputs |
| Reviewer | Claude 3.5 Sonnet | GPT-4o | Precision, validation |
| Formatter | GPT-4o-mini | Haiku | Structured output, speed |

---

## Environment Variables

Required environment variables (set in `.env`):

```bash
# LLM Provider Keys
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
GEMINI_API_KEY=xxx  # Optional

# LiteLLM Configuration
LITELLM_MASTER_KEY=sk-xxx  # Optional, for UI
DATABASE_URL=postgresql://...  # Optional, for cost tracking

# Optional: Local models
OLLAMA_API_BASE=http://localhost:11434
```

---

## Rate Limiting Strategies

### Token-Based Rate Limiting
```python
# In agent code
response = await litellm.acompletion(
    model="agenttwister/payload-engineer",
    messages=messages,
    # Rate limit is handled by LiteLLM config
)
```

### Custom Rate Limiting
```python
import litellm

# Set custom rate limits per request
@litellm.rate_limit(rate_limit="10/minute")
async def generate_with_limit(prompt):
    return await litellm.acompletion(
        model="agenttwister/fast",
        messages=[{"role": "user", "content": prompt}]
    )
```

---

## Fallback Chains

When a model fails, LiteLLM automatically falls back to alternatives

```
agenttwister/analyst
    ↓ (fails)
agenttwister/planner  → (fallback)
    ↓ (fails)
openai/gpt-4o  → (final fallback)
```

### Manual Fallback
```python
import litellm

async def generate_with_fallback(prompt, preferred_model="agenttwister/analyst"):
    fallback_models = ["agenttwister/planner", "openai/gpt-4o"]

    for model in [preferred_model] + fallback_models:
        try:
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response
        except Exception as e:
            continue  # Try next fallback

    raise RuntimeError("All models failed")
```

---

## Cost Tracking

### Automatic Cost Tracking
LiteLLM automatically tracks costs when `model_info` is configured

```python
import litellm

# Enable cost tracking
litellm.success_callback = [log_cost]

def log_cost(model, response, start_time, end_time):
    cost = litellm.completion_cost(response)
    print(f"Model: {model}, Cost: ${cost}, Duration: {end_time - start_time}")
```

### Custom Cost Tracking
```python
# backend/app/services/cost_tracker.py
from datetime import datetime
from typing import Dict

class CostTracker:
    """Track LLM costs per campaign."""

    def __init__(self):
        self.costs: Dict[str, list] = {}

    def track_request(
        self,
        campaign_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float
    ):
        if campaign_id not in self.costs:
            self.costs[campaign_id] = []

        self.costs[campaign_id].append({
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost
        })

    def get_campaign_cost(self, campaign_id: str) -> dict:
        if campaign_id not in self.costs:
            return {"total_cost": 0, "requests": 0}

        requests = self.costs[campaign_id]
        return {
            "total_cost": sum(r["cost"] for r in requests),
            "total_input_tokens": sum(r["input_tokens"] for r in requests),
            "total_output_tokens": sum(r["output_tokens"] for r in requests),
            "requests": len(requests)
        }
```

---

## Streaming Responses

```python
import litellm

async def stream_response(prompt: str, model_alias: str):
    """Stream LLM response token by token."""
    async for chunk in await litellm.acompletion(
        model=model_alias,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    ):
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
```

---

## Testing Configuration

```python
# backend/tests/test_litellm_config.py
import pytest
import litellm

def test_model_alias_available():
    """Test that all configured aliases are available."""
    aliases = [
        "agenttwister/chat-orchestrator",
        "agenttwister/analyst",
        "agenttwister/planner",
        "agenttwister/architect",
        "agenttwister/payload-engineer",
        "agenttwister/reviewer",
        "agenttwister/formatter",
    ]

    for alias in aliases:
        # Test that model can be called (mocked)
        pass

def test_fallback_chain():
    """Test fallback chain works correctly."""
    # Simulate primary model failure
    # Verify fallback is used
    pass
```

---

## Checklist: Adding New Configuration

1. [ ] Add model alias to `model_list` section
2. [ ] Configure `litellm_params` with provider and API key reference
3. [ ] Set `model_info` with token limits and costs
4. [ ] Add to `fallbacks` section if needed
5. [ ] Configure rate limits in `model_params` if needed
6. [ ] Set required environment variables
7. [ ] Test configuration with sample request
8. [ ] Verify cost tracking works
9. [ ] Document model purpose in comments

10. [ ] Update agent code to use new alias

---

## Common Issues

### "Model not found" Error
- **Cause**: Model alias not in config
- **Solution**: Add alias to `litellm_config.yaml`

### Rate Limit Exceeded
- **Cause**: Too many requests per minute
- **Solution**: Increase `rpm` in config or implement request queuing

### Fallback Not Triggering
- **Cause**: Fallback not in fallbacks section
- **Solution**: Add fallback chain for model

### Cost Not Tracked
- **Cause**: Missing `model_info` configuration
- **Solution**: Add `input_cost_per_token` and `output_cost_per_token`

---

## File Locations Reference

| Component | Location |
|-----------|----------|
| Configuration File | `litellm_config.yaml` (project root) |
| Environment Variables | `.env` (project root) |
| Cost Tracker | `backend/app/services/cost_tracker.py` |
| Agent Base Class | `backend/app/agents/base_agent.py` |
