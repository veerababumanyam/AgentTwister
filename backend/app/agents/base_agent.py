"""
Base Agent Class

Google ADK-inspired base agent class with tool binding, memory management,
streaming support, and resilience patterns.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)

from pydantic import BaseModel

from ..database import async_session_maker
from .resilience import ExponentialBackoff, CircuitBreaker, CircuitBreakerConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AgentRole(Enum):
    """Standard agent roles in the AgentTwister pipeline."""
    CHAT_ORCHESTRATOR = "chat_orchestrator"
    ANALYST = "analyst"
    PLANNER = "planner"
    ARCHITECT = "architect"
    PAYLOAD_ENGINEER = "payload_engineer"
    REVIEWER = "reviewer"
    FORMATTER = "formatter"


class AgentState(Enum):
    """Agent execution states."""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentConfig:
    """Configuration for an agent instance."""
    # Identity
    name: str
    role: AgentRole
    version: str = "1.0.0"

    # LLM Configuration (via LiteLLM)
    model_alias: str = "gpt-4o-primary"
    temperature: float = 0.7
    max_tokens: int = 4096

    # Resilience
    max_retries: int = 3
    retry_backoff_initial: float = 1.0
    retry_backoff_max: float = 30.0
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5

    # Memory
    enable_short_term_memory: bool = True
    enable_long_term_memory: bool = True
    memory_collection: str = "agent_memories"

    # Streaming
    enable_streaming: bool = True

    # Timeout
    timeout_seconds: float = 120.0

    # System prompt
    system_prompt: Optional[str] = None


@dataclass
class ToolDefinition:
    """Definition of an available tool for the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema for parameters
    handler: Callable[..., Awaitable[Any]]
    is_dangerous: bool = False  # Tools that modify external state


@dataclass
class AgentContext:
    """Context passed to agent during execution."""
    session_id: str
    campaign_id: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Conversation history
    messages: List[Dict[str, Any]] = field(default_factory=list)

    # Shared context between agents
    shared_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from an agent execution."""
    agent_name: str
    agent_role: AgentRole
    content: str
    state: AgentState
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Tool calls made during execution
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Error information if failed
    error: Optional[str] = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role.value,
            "content": self.content,
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "tool_calls": self.tool_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "error": self.error,
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """
    Base agent class following Google ADK patterns.

    Provides:
    - Tool binding and registration
    - Memory management (short-term and SQLite-backed)
    - Streaming response support
    - Resilience patterns (exponential backoff, circuit breaker)
    - LLM integration via LiteLLM
    - State tracking and logging

    Example:
        class MyAgent(BaseAgent):
            async def process(self, context: AgentContext) -> AgentResponse:
                # Access LLM
                response = await self.llm_generate(
                    "Hello, world!",
                    context=context
                )

                # Use tools
                data = await self.call_tool("database_read", {...})

                return AgentResponse(
                    agent_name=self.config.name,
                    agent_role=self.config.role,
                    content=response,
                    state=AgentState.COMPLETED,
                )
    """

    def __init__(
        self,
        config: AgentConfig,
        tools: Optional[List[ToolDefinition]] = None,
    ):
        """
        Initialize base agent.

        Args:
            config: Agent configuration
            tools: List of available tools for this agent
        """
        self.config = config
        self._tools: Dict[str, ToolDefinition] = {}
        self._state = AgentState.IDLE
        self._db_session = None

        # Setup circuit breaker for LLM calls
        self._circuit_breaker: Optional[CircuitBreaker] = None
        if config.circuit_breaker_enabled:
            self._circuit_breaker = CircuitBreaker(
                name=f"{config.name}_llm",
                config=CircuitBreakerConfig(
                    failure_threshold=config.circuit_breaker_threshold,
                ),
            )

        # Setup backoff strategy
        self._backoff = ExponentialBackoff(
            initial_delay=config.retry_backoff_initial,
            max_delay=config.retry_backoff_max,
            max_attempts=config.max_retries,
        )

        # Register tools
        if tools:
            for tool in tools:
                self.register_tool(tool)

        # Setup system prompt
        self._system_prompt = config.system_prompt or self._default_system_prompt()

        logger.info(f"Agent '{config.name}' initialized (role: {config.role.value})")

    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self._state

    @property
    def tools(self) -> Dict[str, ToolDefinition]:
        """Get registered tools."""
        return self._tools.copy()

    def register_tool(self, tool: ToolDefinition) -> None:
        """
        Register a tool for use by this agent.

        Args:
            tool: Tool definition to register
        """
        self._tools[tool.name] = tool
        logger.debug(f"Agent '{self.config.name}' registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get a registered tool by name."""
        return self._tools.get(name)

    async def call_tool(
        self,
        name: str,
        parameters: Dict[str, Any],
        context: Optional[AgentContext] = None,
    ) -> Any:
        """
        Call a registered tool.

        Args:
            name: Tool name
            parameters: Tool parameters
            context: Agent context (for logging/memory)

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            Exception: If tool execution fails
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found on agent '{self.config.name}'")

        logger.info(
            f"Agent '{self.config.name}' calling tool '{name}' "
            f"with params: {json.dumps(parameters, default=str)[:200]}"
        )

        # Log dangerous tool usage
        if tool.is_dangerous:
            logger.warning(
                f"DANGEROUS TOOL USAGE: Agent '{self.config.name}' "
                f"calling tool '{name}' - verify authorization!"
            )

        try:
            result = await tool.handler(**parameters)

            # Store in context if provided
            if context:
                context.shared_data[f"tool_result_{name}"] = result

            return result
        except Exception as e:
            logger.error(
                f"Agent '{self.config.name}' tool '{name}' failed: {e}",
                exc_info=True,
            )
            raise

    async def llm_generate(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        **kwargs,
    ) -> str:
        """
        Generate LLM response with retry and circuit breaker.

        Args:
            prompt: The prompt to send
            context: Agent context (for conversation history)
            **kwargs: Additional LLM parameters (override config)

        Returns:
            Generated text response

        Raises:
            Exception: If all retries exhausted or circuit open
        """
        # Build messages from context
        messages = []

        # Add system prompt
        system_prompt = kwargs.pop("system_prompt", self._system_prompt)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        if context and context.messages:
            messages.extend(context.messages)

        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        # Merge parameters
        params = {
            "model": self.config.model_alias,
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            "messages": messages,
            **kwargs,
        }

        async def _call_llm() -> str:
            """Actual LLM call (for retry/circuit wrapper)."""
            from .tools import HTTPCallerTool
            http_tool = HTTPCallerTool()

            # Call LiteLLM gateway
            llm_response = await http_tool.call(
                url="http://localhost:4000/v1/chat/completions",  # LiteLLM proxy
                method="POST",
                json_body=params,
                headers={"Content-Type": "application/json"},
            )

            if llm_response.get("error"):
                raise Exception(f"LLM error: {llm_response['error']}")

            return llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Apply circuit breaker if enabled
        if self._circuit_breaker:
            try:
                return await self._circuit_breaker.call(_call_llm)
            except Exception as e:
                if "CircuitBreakerOpenError" in str(type(e)):
                    raise
                # Retry on other errors
                pass

        # Apply retry with backoff
        last_error = None
        async for attempt in self._backoff:
            try:
                return await _call_llm()
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Agent '{self.config.name}' LLM call attempt "
                    f"{attempt + 1}/{self._backoff.max_attempts} failed: {e}"
                )

        raise last_error or Exception("LLM call failed")

    async def llm_generate_stream(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Generate streaming LLM response.

        Args:
            prompt: The prompt to send
            context: Agent context
            **kwargs: Additional LLM parameters

        Yields:
            Streaming text chunks
        """
        # Build messages
        messages = []

        system_prompt = kwargs.pop("system_prompt", self._system_prompt)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if context and context.messages:
            messages.extend(context.messages)

        messages.append({"role": "user", "content": prompt})

        params = {
            "model": self.config.model_alias,
            "temperature": kwargs.pop("temperature", self.config.temperature),
            "max_tokens": kwargs.pop("max_tokens", self.config.max_tokens),
            "messages": messages,
            "stream": True,
            **kwargs,
        }

        # Streaming implementation
        from .tools import HTTPCallerTool
        http_tool = HTTPCallerTool()

        async for chunk in http_tool.call_stream(
            url="http://localhost:4000/v1/chat/completions",
            json_body=params,
        ):
            if chunk:
                yield chunk

    async def save_to_memory(
        self,
        key: str,
        value: Any,
        context: AgentContext,
    ) -> None:
        """
        Save data to agent memory (SQLite).

        Args:
            key: Memory key
            value: Value to store (will be JSON serialized)
            context: Agent context with session/campaign IDs
        """
        if not self.config.enable_long_term_memory:
            return

        # Use SQLite via async session
        async with async_session_maker() as session:
            # Store in a simple key-value approach using JSON
            # In production, you'd have a dedicated AgentMemory table
            import json
            from sqlalchemy import text

            # For now, store in shared_data as JSON
            context.shared_data[f"memory_{key}"] = value
            logger.debug(f"Agent '{self.config.name}' saved to memory: {key}")

    async def load_from_memory(
        self,
        key: str,
        context: AgentContext,
    ) -> Optional[Any]:
        """
        Load data from agent memory.

        Args:
            key: Memory key
            context: Agent context

        Returns:
            Stored value or None if not found
        """
        if not self.config.enable_long_term_memory:
            return None

        # For now, retrieve from shared_data
        return context.shared_data.get(f"memory_{key}")

    async def execute(
        self,
        input_data: Union[str, Dict[str, Any]],
        context: Optional[AgentContext] = None,
    ) -> AgentResponse:
        """
        Execute the agent's main task.

        This is the primary entry point for agent execution.

        Args:
            input_data: Input prompt or structured data
            context: Agent context

        Returns:
            Agent response
        """
        self._state = AgentState.THINKING
        start_time = datetime.utcnow()

        # Create default context if needed
        if context is None:
            context = AgentContext(session_id=f"session_{start_time.timestamp()}")

        try:
            # Update context with input message
            if isinstance(input_data, str):
                context.messages.append({
                    "role": "user",
                    "content": input_data,
                })
                input_data = {"prompt": input_data}

            # Run agent processing
            self._state = AgentState.EXECUTING
            response = await self.process(context, input_data)

            # Record completion time
            duration = (datetime.utcnow() - start_time).total_seconds()
            response.metadata["duration_seconds"] = duration

            self._state = AgentState.COMPLETED
            return response

        except Exception as e:
            self._state = AgentState.FAILED
            logger.error(
                f"Agent '{self.config.name}' execution failed: {e}",
                exc_info=True,
            )
            return AgentResponse(
                agent_name=self.config.name,
                agent_role=self.config.role,
                content="",
                state=AgentState.FAILED,
                error=str(e),
            )

    @abstractmethod
    async def process(
        self,
        context: AgentContext,
        input_data: Dict[str, Any],
    ) -> AgentResponse:
        """
        Process the agent's main task.

        Subclasses must implement this method with their specific logic.

        Args:
            context: Agent context with conversation history and shared data
            input_data: Structured input data

        Returns:
            Agent response
        """
        raise NotImplementedError("Subclasses must implement process()")

    def _default_system_prompt(self) -> str:
        """Get default system prompt based on agent role."""
        base_prompt = """You are an AI security research assistant within the AgentTwister platform.

Your purpose is to assist authorized security researchers in testing AI systems for vulnerabilities.

IMPORTANT:
- All testing must be authorized and scoped
- Report findings responsibly
- Follow ethical disclosure guidelines
- Never generate real exploits for production systems without authorization
"""

        role_specific = {
            AgentRole.CHAT_ORCHESTRATOR: """As the Chat Orchestrator, your role is to:
1. Understand user intent from natural language
2. Ask clarifying questions when needed
3. Route tasks to appropriate specialist agents
4. Present results clearly in the chat interface""",

            AgentRole.ANALYST: """As the Analyst agent, your role is to:
1. Parse and analyze uploaded documents
2. Extract target system context and tech stack
3. Identify relevant attack surfaces
4. Summarize findings for the Planner agent""",

            AgentRole.PLANNER: """As the Planner agent, your role is to:
1. Select applicable attack vectors from the UC library
2. Prioritize by impact and likelihood
3. Generate a structured campaign plan
4. Consider constraints and scope limitations""",

            AgentRole.ARCHITECT: """As the Architect agent, your role is to:
1. Determine optimal payload placement strategies
2. Select appropriate stealth encoding techniques
3. Design payload architecture for maximum effectiveness
4. Ensure coherence with visible content""",

            AgentRole.PAYLOAD_ENGINEER: """As the Payload Engineer agent, your role is to:
1. Generate customized payloads from templates
2. Apply stealth encoding techniques
3. Ensure semantic coherence
4. Document payload metadata""",

            AgentRole.REVIEWER: """As the Reviewer agent, your role is to:
1. Validate payload correctness
2. Assess human invisibility (stealth score)
3. Verify LLM legibility
4. Flag any issues for rework""",

            AgentRole.FORMATTER: """As the Formatter agent, your role is to:
1. Assemble final documents (DOCX/PDF)
2. Generate payload manifests
3. Create preview artifacts
4. Prepare evidence bundles""",
        }

        return base_prompt + role_specific.get(
            self.config.role,
            "Follow the user's instructions within security research guidelines.",
        )
