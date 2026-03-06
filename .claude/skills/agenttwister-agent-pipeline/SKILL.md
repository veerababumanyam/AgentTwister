---
name: agenttwister-agent-pipeline
description: Use when building or modifying multi-agent pipelines with Google ADK (Agent Development Kit), A2A (Agent-to-Agent) protocol, tool binding, memory management, or multi-agent orchestration patterns. Triggers for tasks involving agent scaffolding, tool registration, inter-agent communication, LiteLLM integration patterns, or the 7-agent pipeline architecture (Analyst, Planner, Architect, Payload Engineer, Reviewer, Formatter, Chat Orchestrator).
---

# Agent Pipeline Development

A comprehensive guide for building production-grade multi-agent pipelines using Google ADK and A2A Protocol, specifically designed for the AgentTwister security research platform.

## Architecture Overview

AgentTwister uses a **7-agent pipeline** orchestrated through the A2A protocol:

```
┌─────────────────┐
│ Chat Orchestrator│  ← Entry point, intent classification
└────────┬────────┘
         │ A2A dispatch
         ▼
┌─────────────────┐
│    Analyst      │  ← Target analysis, vector selection
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Planner      │  ← Attack plan generation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Architect     │  ← Payload placement strategy
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Payload Engineer │  ← Payload generation & embedding
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Reviewer      │  ← Stealth scoring, validation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Formatter     │  ← Document assembly, export
└─────────────────┘
```

---

## Agent Base Class

All agents inherit from `BaseAgent` located at `backend/app/agents/base_agent.py`:

```python
from google.adk.agents import Agent
from google.adk.tools import Tool
from typing import Dict, Any, Optional
import litellm

class BaseAgent(Agent):
    """
    Base class for all AgentTwister pipeline agents.

    Features:
    - Tool binding via register_tool() and call_tool()
    - LLM integration through LiteLLM (llm_generate())
    - Resilience patterns (circuit breaker, exponential backoff)
    - Memory management (short-term and Firestore-backed)
    """

    def __init__(
        self,
        agent_id: str,
        model_alias: str,  # References litellm_config.yaml
        memory_enabled: bool = True,
        tools: Optional[list[Tool]] = None
    ):
        super().__init__(agent_id=agent_id)
        self.model_alias = model_alias
        self.memory_enabled = memory_enabled
        self._tools_registry: Dict[str, Tool] = {}

        # Resilience patterns
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout_seconds=60
        )
        self.backoff = ExponentialBackoff(
            initial_delay=1.0,
            max_delay=60.0,
            multiplier=2.0
        )

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for this agent."""
        self._tools_registry[tool.name] = tool

    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """Execute a registered tool with resilience."""
        if tool_name not in self._tools_registry:
            raise ValueError(f"Tool '{tool_name}' not registered")

        return await self.circuit_breaker.execute(
            lambda: self._tools_registry[tool_name].execute(**kwargs)
        )

    async def llm_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Generate LLM response via LiteLLM gateway.

        Uses model alias from litellm_config.yaml for hot-swap capability.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await litellm.acompletion(
                model=self.model_alias,
                messages=messages,
                temperature=temperature,
                stream=stream
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to retry with backoff
            await self.backoff.wait()
            # Retry logic here...
```

---

## A2A Protocol Integration

Agents communicate via the **Google Agent-to-Agent (A2A) Protocol**. Each agent exposes an HTTP endpoint and consumes others' endpoints.

### A2A Task Message Format

```python
# backend/app/agents/a2a/protocol.py
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class A2ATaskMessage(BaseModel):
    """Standard A2A task message format."""
    task_id: str
    sender_agent_id: str
    recipient_agent_id: str
    input_context: Dict[str, Any]
    required_output_schema: Optional[Dict] = None
    timestamp: datetime = datetime.utcnow()
```

### A2A Adapter

```python
# backend/app/agents/a2a/adapter.py
import httpx
from typing import Dict, Any

class A2AAdapter:
    """
    HTTP-based A2A protocol adapter for inter-agent communication.
    """
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def dispatch(self, task: A2ATaskMessage) -> Dict[str, Any]:
        """Dispatch task to recipient agent via HTTP."""
        url = f"{self.base_url}/a2a/{task.recipient_agent_id}/tasks"
        response = await self.client.post(url, json=task.dict())
        return response.json()

    async def get_status(self, task_id: str, agent_id: str) -> Dict[str, Any]:
        """Check status of dispatched task."""
        url = f"{self.base_url}/a2a/{agent_id}/tasks/{task_id}"
        response = await self.client.get(url)
        return response.json()
```

---

## LiteLLM Configuration

Model aliases are defined in `litellm_config.yaml` at project root:

```yaml
model_list:
  # Chat Orchestrator - fast classification
  - model_name: agenttwister/chat-orchestrator
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY

  # Analyst - deep analysis
  - model_name: agenttwister/analyst
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # Planner - strategic planning
  - model_name: agenttwister/planner
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # Architect - system design
  - model_name: agenttwister/architect
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # Payload Engineer - creative payload generation
  - model_name: agenttwister/payload-engineer
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  # Reviewer - precision scoring
  - model_name: agenttwister/reviewer
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # Formatter - structured output
  - model_name: agenttwister/formatter
    litellm_params:
      model: openai/gpt-4o-mini
      api_key: os.environ/OPENAI_API_KEY
```

---

## Resilience Patterns

```python
# backend/app/agents/resilience/circuit_breaker.py
from typing import Callable, Any
import asyncio

class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.
    Opens after 5 consecutive failures, resets after 60 seconds.
    """
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    async def execute(self, operation: Callable[[], Any]) -> Any:
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = await operation()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = datetime.now() - self.last_failure_time
        return elapsed.seconds >= self.timeout_seconds
```

```python
# backend/app/agents/resilience/exponential_backoff.py
import random
import asyncio

class ExponentialBackoff:
    """
    Exponential backoff with jitter for retries.
    """
    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0
    ):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.current_delay = initial_delay
        self.attempts = 0

    async def wait(self) -> float:
        jitter = random.uniform(0.75, 1.25)
        delay = min(self.current_delay * jitter, self.max_delay)
        await asyncio.sleep(delay)
        self.current_delay = min(
            self.current_delay * self.multiplier,
            self.max_delay
        )
        self.attempts += 1
        return delay

    def reset(self):
        self.current_delay = self.initial_delay
        self.attempts = 0
```

---

## Checklist: Creating a New Agent

When adding a new agent to the pipeline:

1. [ ] Create agent class inheriting from `BaseAgent`
2. [ ] Define `agent_id` and `model_alias` matching `litellm_config.yaml`
3. [ ] Register required tools in `__init__`
4. [ ] Implement primary method (e.g., `analyze()`, `plan()`, `generate()`)
5. [ ] Add A2A endpoint in `backend/app/api/routes/`
6. [ ] Register endpoint in `agent_endpoints` dict in A2A adapter
7. [ ] Add model alias to `litellm_config.yaml` if new model needed
8. [ ] Write unit tests in `backend/tests/`
9. [ ] Document agent's role in docstring

---

## File Locations Reference

| Component | Location |
|-----------|----------|
| Base Agent | `backend/app/agents/base_agent.py` |
| Agent Registry | `backend/app/agents/registry.py` |
| A2A Protocol | `backend/app/agents/a2a/protocol.py` |
| A2A Adapter | `backend/app/agents/a2a/adapter.py` |
| Resilience | `backend/app/agents/resilience/` |
| Tools | `backend/app/agents/tools/` |
| LiteLLM Config | `litellm_config.yaml` (project root) |
