"""
A2A (Agent-to-Agent) Protocol Adapter

Implements the Google A2A Protocol for standardized inter-agent communication.
This enables agents to discover, invoke, and respond to each other regardless of
their internal implementation.

Key features:
- Message format standardization
- Service discovery and registration
- Task dispatch and response handling
- Streaming support for long-running tasks
- Error handling and retry logic
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
)

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================
# A2A STATUS CODES
# ============================================================

class A2AStatusCode(str, Enum):
    """Status codes for A2A responses."""
    # Success codes
    OK = "ok"  # Request completed successfully
    ACCEPTED = "accepted"  # Request accepted for processing
    PARTIAL = "partial"  # Partial results available

    # Client error codes
    BAD_REQUEST = "bad_request"  # Invalid request format
    UNAUTHORIZED = "unauthorized"  # Authentication/authorization failed
    FORBIDDEN = "forbidden"  # Operation not allowed
    NOT_FOUND = "not_found"  # Agent or resource not found
    INVALID_INPUT = "invalid_input"  # Invalid input parameters
    TIMEOUT = "timeout"  # Request timed out

    # Server error codes
    INTERNAL_ERROR = "internal_error"  # Unexpected server error
    SERVICE_UNAVAILABLE = "service_unavailable"  # Agent temporarily unavailable
    TOOL_ERROR = "tool_error"  # Tool execution failed


# ============================================================
# A2A MESSAGE MODELS
# ============================================================

class A2AMessageHeader(BaseModel):
    """Header for A2A messages."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_agent: str  # Agent sending the message
    target_agent: str  # Agent receiving the message (or "*" for broadcast)
    conversation_id: Optional[str] = None  # Thread ID for multi-turn conversations
    reply_to: Optional[str] = None  # Message ID this is a reply to


class A2ATaskInput(BaseModel):
    """Input data for a task."""
    type: str  # Task type (e.g., "analyze", "generate", "validate")
    data: Dict[str, Any]  # Task-specific data
    schema_version: str = "1.0"  # Schema version for compatibility


class A2ATaskOutput(BaseModel):
    """Output data from a task."""
    type: str  # Output type
    data: Dict[str, Any]  # Output data
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Additional metadata


class A2AToolCall(BaseModel):
    """Record of a tool call made during execution."""
    tool_name: str
    parameters: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class A2AStatusCodeDetail(BaseModel):
    """Detailed status information."""
    code: A2AStatusCode
    message: str
    details: Optional[Dict[str, Any]] = None


class A2AMessage(BaseModel):
    """
    A2A Protocol message format.

    This is the standard message format for inter-agent communication
    following the Google A2A Protocol specification.
    """
    header: A2AMessageHeader
    task: Optional[A2ATaskInput] = None  # For task messages
    result: Optional[A2ATaskOutput] = None  # For result messages
    status: A2AStatusCodeDetail  # Always present
    tool_calls: List[A2AToolCall] = Field(default_factory=list)
    streaming: bool = False  # Whether this is part of a streaming response
    stream_index: Optional[int] = None  # Position in stream if streaming

    class Config:
        use_enum_values = True


# ============================================================
# A2A PROTOCOL ADAPTER
# ============================================================

@dataclass
class AgentEndpoint:
    """Registered agent endpoint for A2A communication."""
    agent_name: str
    agent_role: str
    url: str  # A2A endpoint URL
    methods: List[str]  # Supported task types
    version: str
    capabilities: Dict[str, Any] = field(default_factory=dict)


@dataclass
class A2AConfig:
    """Configuration for A2A protocol adapter."""
    # Local agent identity
    agent_name: str
    agent_role: str
    agent_version: str = "1.0.0"

    # Service discovery
    registry_url: Optional[str] = None  # URL of service registry (if using central registry)

    # Networking
    host: str = "localhost"
    port: int = 8000
    use_https: bool = False

    # Timeouts
    request_timeout: float = 120.0
    discovery_timeout: float = 10.0

    # Retry
    max_retries: int = 3
    retry_delay: float = 1.0

    @property
    def base_url(self) -> str:
        """Get base URL for this agent."""
        scheme = "https" if self.use_https else "http"
        return f"{scheme}://{self.host}:{self.port}"


class A2AProtocolAdapter:
    """
    Adapter for Google A2A Protocol communication.

    Provides:
    - Message construction and validation
    - Agent discovery and registration
    - Task dispatch to other agents
    - Response handling and streaming
    - Service health checking

    Example:
        adapter = A2AProtocolAdapter(config=A2AConfig(agent_name="planner"))

        # Send task to another agent
        response = await adapter.send_task(
            target_agent="analyst",
            task_type="analyze",
            data={"content": "Analyze this..."}
        )

        # Stream response
        async for chunk in adapter.send_task_stream(...):
            print(chunk)
    """

    def __init__(self, config: A2AConfig):
        """
        Initialize A2A protocol adapter.

        Args:
            config: A2A configuration
        """
        self.config = config
        self._endpoints: Dict[str, AgentEndpoint] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._active_streams: Dict[str, asyncio.Queue] = {}

        # Import HTTP tool for making requests
        from ..tools import HTTPCallerTool
        self._http = HTTPCallerTool()

        logger.info(
            f"A2A adapter initialized for '{config.agent_name}' "
            f"(role: {config.agent_role})"
        )

    async def register_agent(
        self,
        agent_name: str,
        agent_role: str,
        url: str,
        methods: List[str],
        version: str = "1.0.0",
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register an agent endpoint for A2A communication.

        Args:
            agent_name: Name of the agent
            agent_role: Role of the agent
            url: A2A endpoint URL
            methods: Supported task types
            version: Agent version
            capabilities: Additional capabilities metadata
        """
        endpoint = AgentEndpoint(
            agent_name=agent_name,
            agent_role=agent_role,
            url=url,
            methods=methods,
            version=version,
            capabilities=capabilities or {},
        )
        self._endpoints[agent_name] = endpoint
        logger.info(f"Registered A2A endpoint: {agent_name} -> {url}")

    def unregister_agent(self, agent_name: str) -> None:
        """Unregister an agent endpoint."""
        if agent_name in self._endpoints:
            del self._endpoints[agent_name]
            logger.info(f"Unregistered A2A endpoint: {agent_name}")

    def get_endpoint(self, agent_name: str) -> Optional[AgentEndpoint]:
        """Get registered endpoint for an agent."""
        return self._endpoints.get(agent_name)

    def list_endpoints(self) -> List[AgentEndpoint]:
        """List all registered endpoints."""
        return list(self._endpoints.values())

    def discover_agents(self, registry_url: Optional[str] = None) -> List[AgentEndpoint]:
        """
        Discover agents from a service registry.

        Args:
            registry_url: URL of registry (uses config default if None)

        Returns:
            List of discovered agent endpoints
        """
        # In a full implementation, this would query a service registry
        # For now, return locally registered endpoints
        logger.debug(f"Agent discovery: {len(self._endpoints)} local endpoints")
        return self.list_endpoints()

    async def send_task(
        self,
        target_agent: str,
        task_type: str,
        data: Dict[str, Any],
        conversation_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> A2AMessage:
        """
        Send a task to another agent via A2A protocol.

        Args:
            target_agent: Name of agent to send to
            task_type: Type of task
            data: Task data
            conversation_id: Optional conversation thread ID
            timeout: Request timeout

        Returns:
            Response message from target agent

        Raises:
            ValueError: If target agent not found
            TimeoutError: If request times out
        """
        endpoint = self.get_endpoint(target_agent)
        if not endpoint:
            # Try to discover the agent
            self.discover_agents()
            endpoint = self.get_endpoint(target_agent)
            if not endpoint:
                raise ValueError(f"Agent '{target_agent}' not found")

        # Build message
        message = A2AMessage(
            header=A2AMessageHeader(
                source_agent=self.config.agent_name,
                target_agent=target_agent,
                conversation_id=conversation_id,
            ),
            task=A2ATaskInput(
                type=task_type,
                data=data,
            ),
            status=A2AStatusCodeDetail(
                code=A2AStatusCode.OK,
                message="Task dispatch",
            ),
        )

        logger.info(
            f"A2A sending task: {self.config.agent_name} -> {target_agent} "
            f"(type: {task_type})"
        )

        # Send request
        try:
            response_data = await self._http.call(
                url=endpoint.url,
                method="POST",
                json_body=message.dict(),
                timeout=timeout or self.config.request_timeout,
            )

            if not response_data.get("success"):
                raise Exception(f"HTTP error: {response_data.get('status_code')}")

            # Parse response
            response = A2AMessage(**response_data["body"])
            logger.debug(f"A2A response: {response.status.code}")
            return response

        except Exception as e:
            logger.error(f"A2A task failed: {e}")
            return A2AMessage(
                header=A2AMessageHeader(
                    source_agent=target_agent,
                    target_agent=self.config.agent_name,
                    reply_to=message.header.message_id,
                ),
                status=A2AStatusCodeDetail(
                    code=A2AStatusCode.INTERNAL_ERROR,
                    message=str(e),
                ),
            )

    async def send_task_stream(
        self,
        target_agent: str,
        task_type: str,
        data: Dict[str, Any],
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[A2AMessage]:
        """
        Send a task with streaming response.

        Args:
            target_agent: Name of agent to send to
            task_type: Type of task
            data: Task data
            conversation_id: Optional conversation thread ID

        Yields:
            Response message chunks as they arrive
        """
        endpoint = self.get_endpoint(target_agent)
        if not endpoint:
            raise ValueError(f"Agent '{target_agent}' not found")

        # Build message
        message = A2AMessage(
            header=A2AMessageHeader(
                source_agent=self.config.agent_name,
                target_agent=target_agent,
                conversation_id=conversation_id,
            ),
            task=A2ATaskInput(
                type=task_type,
                data=data,
            ),
            status=A2AStatusCodeDetail(
                code=A2AStatusCode.OK,
                message="Streaming task dispatch",
            ),
        )

        logger.info(f"A2A sending streaming task: {self.config.agent_name} -> {target_agent}")

        # Stream response
        buffer = ""
        async for chunk in self._http.call_stream(
            url=endpoint.url,
            json_body=message.dict(),
            headers={"Accept": "text/event-stream"},
        ):
            buffer += chunk

            # Try to parse complete JSON messages
            while buffer:
                try:
                    # Find JSON object boundary
                    obj_end = buffer.find("}\n")
                    if obj_end == -1:
                        # Try finding just }
                        obj_end = buffer.find("}")
                    if obj_end == -1:
                        break

                    json_str = buffer[:obj_end + 1]
                    buffer = buffer[obj_end + 1:].lstrip()

                    parsed = json.loads(json_str)
                    yield A2AMessage(**parsed)

                except json.JSONDecodeError:
                    # Not a complete JSON object yet
                    break

    async def broadcast(
        self,
        task_type: str,
        data: Dict[str, Any],
        exclude: Optional[List[str]] = None,
    ) -> Dict[str, A2AMessage]:
        """
        Broadcast a task to all registered agents.

        Args:
            task_type: Type of task
            data: Task data
            exclude: Agents to exclude from broadcast

        Returns:
            Dict mapping agent names to their responses
        """
        exclude = exclude or []
        results = {}

        for endpoint in self.list_endpoints():
            if endpoint.agent_name in exclude or endpoint.agent_name == self.config.agent_name:
                continue

            if task_type in endpoint.methods or "*" in endpoint.methods:
                try:
                    response = await self.send_task(
                        target_agent=endpoint.agent_name,
                        task_type=task_type,
                        data=data,
                    )
                    results[endpoint.agent_name] = response
                except Exception as e:
                    logger.error(f"Broadcast to {endpoint.agent_name} failed: {e}")
                    results[endpoint.agent_name] = A2AMessage(
                        header=A2AMessageHeader(
                            source_agent=endpoint.agent_name,
                            target_agent=self.config.agent_name,
                        ),
                        status=A2AStatusCodeDetail(
                            code=A2AStatusCode.INTERNAL_ERROR,
                            message=str(e),
                        ),
                    )

        return results

    async def check_health(self, agent_name: str) -> bool:
        """
        Check if an agent is healthy and responding.

        Args:
            agent_name: Name of agent to check

        Returns:
            True if agent is healthy
        """
        endpoint = self.get_endpoint(agent_name)
        if not endpoint:
            return False

        try:
            response = await self._http.call(
                url=f"{endpoint.url}/health",
                method="GET",
                timeout=5.0,
            )
            return response.get("success", False)
        except Exception:
            return False

    def create_response(
        self,
        request: A2AMessage,
        status_code: A2AStatusCode = A2AStatusCode.OK,
        status_message: str = "OK",
        output_data: Optional[Dict[str, Any]] = None,
        output_type: str = "result",
        tool_calls: Optional[List[A2AToolCall]] = None,
    ) -> A2AMessage:
        """
        Create a response message for a request.

        Args:
            request: Original request message
            status_code: Response status code
            status_message: Status message
            output_data: Output data
            output_type: Output type identifier
            tool_calls: Tool calls made during processing

        Returns:
            Response message
        """
        return A2AMessage(
            header=A2AMessageHeader(
                source_agent=self.config.agent_name,
                target_agent=request.header.source_agent,
                conversation_id=request.header.conversation_id,
                reply_to=request.header.message_id,
            ),
            result=A2ATaskOutput(
                type=output_type,
                data=output_data or {},
            ) if output_data else None,
            status=A2AStatusCodeDetail(
                code=status_code,
                message=status_message,
            ),
            tool_calls=tool_calls or [],
        )

    async def handle_request(
        self,
        message: A2AMessage,
        handler: Callable[[A2ATaskInput], Any],
    ) -> A2AMessage:
        """
        Handle an incoming A2A request.

        Args:
            message: Incoming request message
            handler: Handler function for the task

        Returns:
            Response message
        """
        if not message.task:
            return self.create_response(
                message,
                A2AStatusCode.BAD_REQUEST,
                "No task data in message",
            )

        try:
            result = await handler(message.task)
            return self.create_response(
                message,
                A2AStatusCode.OK,
                "Task completed",
                output_data=result.data if isinstance(result, A2ATaskOutput) else result,
                output_type=result.type if isinstance(result, A2ATaskOutput) else "result",
            )

        except Exception as e:
            logger.error(f"Error handling A2A request: {e}", exc_info=True)
            return self.create_response(
                message,
                A2AStatusCode.INTERNAL_ERROR,
                str(e),
            )

    async def close(self) -> None:
        """Close A2A adapter resources."""
        await self._http.close()
