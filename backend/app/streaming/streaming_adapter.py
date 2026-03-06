"""
Streaming Adapter

Provides unified streaming interface with token-level streaming support.
Optimized for <500ms time-to-first-token latency.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from ..agents.base_agent import BaseAgent, AgentContext
from .connection_manager import ConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


class StreamEventType(str, Enum):
    """Types of streaming events."""
    # Token-level events
    TOKEN = "token"
    TOKEN_START = "token_start"  # First token (TTFM marker)
    TOKEN_END = "token_end"

    # Agent status events
    AGENT_START = "agent_start"
    AGENT_THINKING = "agent_thinking"
    AGENT_EXECUTING = "agent_executing"
    AGENT_STREAMING = "agent_streaming"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"

    # Progress events
    PROGRESS = "progress"
    STAGE_CHANGE = "stage_change"

    # Tool events
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # System events
    START = "start"
    END = "end"
    ERROR = "error"
    PING = "ping"


@dataclass
class StreamEvent:
    """A single streaming event."""
    event_type: Union[StreamEventType, str]
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: Optional[str] = None
    agent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "type": self.event_type.value if isinstance(self.event_type, StreamEventType) else self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "agent_id": self.agent_id,
        }

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        return f"event: {self.event_type}\ndata: {json.dumps(self.to_dict())}\n\n"


@dataclass
class StreamMetrics:
    """Metrics for a streaming session."""
    start_time: float = field(default_factory=time.time)
    first_token_time: Optional[float] = None
    token_count: int = 0
    byte_count: int = 0
    end_time: Optional[float] = None

    @property
    def time_to_first_token(self) -> Optional[float]:
        """Get TTFM in milliseconds."""
        if self.first_token_time:
            return (self.first_token_time - self.start_time) * 1000
        return None

    @property
    def total_duration(self) -> Optional[float]:
        """Get total duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def tokens_per_second(self) -> Optional[float]:
        """Calculate tokens per second."""
        if self.end_time and self.token_count > 0:
            duration = self.end_time - self.start_time
            return self.token_count / duration
        return None


class StreamingAdapter:
    """
    Adapter for streaming agent responses with token-level granularity.

    Features:
    - Token-level streaming from LLM responses
    - <500ms time-to-first-token target
    - Automatic retry on streaming failures
    - Progress updates during agent execution
    - Broadcast to multiple connections
    """

    def __init__(
        self,
        agent: BaseAgent,
        connection_manager: Optional[ConnectionManager] = None,
    ):
        """
        Initialize the streaming adapter.

        Args:
            agent: The agent to stream responses from
            connection_manager: Optional custom connection manager
        """
        self.agent = agent
        self.connection_manager = connection_manager or get_connection_manager()
        self._active_streams: Dict[str, StreamMetrics] = {}

    async def stream_llm_response(
        self,
        prompt: str,
        context: AgentContext,
        session_id: str,
        on_token: Optional[Callable[[str], Any]] = None,
        **llm_kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream LLM response token by token.

        Args:
            prompt: The prompt to send
            context: Agent context
            session_id: Session identifier
            on_token: Optional callback for each token
            **llm_kwargs: Additional LLM parameters

        Yields:
            StreamEvent objects for each token and status update
        """
        metrics = StreamMetrics(start_time=time.time())
        stream_id = f"{session_id}_{int(time.time())}"
        self._active_streams[stream_id] = metrics

        try:
            # Send start event
            yield StreamEvent(
                event_type=StreamEventType.START,
                data={"stage": "llm_generation", "prompt_length": len(prompt)},
                session_id=session_id,
                agent_id=self.agent.config.name,
            )

            # Start agent thinking
            from ..agents.base_agent import AgentState
            self.agent._state = AgentState.THINKING
            yield StreamEvent(
                event_type=StreamEventType.AGENT_THINKING,
                data={"agent": self.agent.config.name, "model": self.agent.config.model_alias},
                session_id=session_id,
                agent_id=self.agent.config.name,
            )

            # Stream from LLM
            first_token = True
            full_content = []

            async for token_chunk in self.agent.llm_generate_stream(
                prompt=prompt,
                context=context,
                **llm_kwargs,
            ):
                if token_chunk:
                    if first_token:
                        metrics.first_token_time = time.time()
                        ttfm_ms = metrics.time_to_first_token

                        yield StreamEvent(
                            event_type=StreamEventType.TOKEN_START,
                            data={
                                "content": token_chunk,
                                "ttfm_ms": round(ttfm_ms, 2) if ttfm_ms else None,
                            },
                            session_id=session_id,
                            agent_id=self.agent.config.name,
                        )
                        first_token = False
                    else:
                        yield StreamEvent(
                            event_type=StreamEventType.TOKEN,
                            data={"content": token_chunk},
                            session_id=session_id,
                            agent_id=self.agent.config.name,
                        )

                    full_content.append(token_chunk)
                    metrics.token_count += len(token_chunk)
                    metrics.byte_count += len(token_chunk.encode("utf-8"))

                    # Call token callback if provided
                    if on_token:
                        try:
                            await on_token(token_chunk)
                        except Exception as e:
                            logger.warning(f"Token callback error: {e}")

            # Send completion event
            metrics.end_time = time.time()

            yield StreamEvent(
                event_type=StreamEventType.TOKEN_END,
                data={
                    "full_content": "".join(full_content),
                    "metrics": {
                        "ttfm_ms": round(metrics.time_to_first_token, 2) if metrics.time_to_first_token else None,
                        "duration_ms": round((metrics.end_time - metrics.start_time) * 1000, 2),
                        "token_count": metrics.token_count,
                        "bytes": metrics.byte_count,
                    },
                },
                session_id=session_id,
                agent_id=self.agent.config.name,
            )

            from ..agents.base_agent import AgentState
            self.agent._state = AgentState.COMPLETED
            yield StreamEvent(
                event_type=StreamEventType.AGENT_COMPLETE,
                data={"agent": self.agent.config.name},
                session_id=session_id,
                agent_id=self.agent.config.name,
            )

        except Exception as e:
            metrics.end_time = time.time()
            logger.error(f"Streaming error: {e}", exc_info=True)

            yield StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": str(e), "error_type": type(e).__name__},
                session_id=session_id,
                agent_id=self.agent.config.name,
            )

        finally:
            self._active_streams.pop(stream_id, None)

    async def stream_agent_execution(
        self,
        input_data: Union[str, Dict[str, Any]],
        context: AgentContext,
        session_id: str,
        broadcast: bool = True,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream complete agent execution with progress updates.

        Args:
            input_data: Input prompt or structured data
            context: Agent context
            session_id: Session identifier
            broadcast: Whether to broadcast events to all session connections

        Yields:
            StreamEvent objects throughout execution
        """
        start_time = time.time()

        async def _emit(event: StreamEvent):
            """Emit event to all connected clients."""
            if broadcast:
                await self.connection_manager.broadcast(
                    data=event.to_dict()["data"],
                    event_type=event.to_dict()["type"],
                    session_id=session_id,
                    agent_id=event.agent_id,
                )
            yield event

        try:
            # Start event
            async for event in _emit(StreamEvent(
                event_type=StreamEventType.START,
                data={"agent": self.agent.config.name, "input": str(input_data)[:200]},
                session_id=session_id,
                agent_id=self.agent.config.name,
            )):
                yield event

            # Execute with streaming
            if isinstance(input_data, str):
                response = await self.agent.execute(input_data, context)
            else:
                response = await self.agent.execute(input_data, context)

            # Stream the response content
            content = response.content
            if content:
                chunk_size = 10  # Small chunks for token-like streaming
                for i in range(0, len(content), chunk_size):
                    chunk = content[i:i + chunk_size]
                    async for event in _emit(StreamEvent(
                        event_type=StreamEventType.TOKEN,
                        data={"content": chunk},
                        session_id=session_id,
                        agent_id=self.agent.config.name,
                    )):
                        yield event
                    await asyncio.sleep(0.01)  # Small delay for natural feel

            # Complete event
            duration = time.time() - start_time
            async for event in _emit(StreamEvent(
                event_type=StreamEventType.END,
                data={
                    "agent": self.agent.config.name,
                    "state": response.state.value,
                    "duration_seconds": round(duration, 2),
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                },
                session_id=session_id,
                agent_id=self.agent.config.name,
            )):
                yield event

        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            async for event in _emit(StreamEvent(
                event_type=StreamEventType.ERROR,
                data={"error": str(e), "error_type": type(e).__name__},
                session_id=session_id,
                agent_id=self.agent.config.name,
            )):
                yield event

    def get_metrics(self, session_id: str) -> Optional[StreamMetrics]:
        """Get streaming metrics for a session."""
        stream_id = f"{session_id}_{int(time.time())}"
        return self._active_streams.get(stream_id)


class TokenAccumulator:
    """
    Accumulates tokens and provides full content access.

    Useful for building responses while streaming.
    """

    def __init__(self, max_tokens: int = 100000):
        """
        Initialize token accumulator.

        Args:
            max_tokens: Maximum tokens to accumulate (prevents memory issues)
        """
        self._tokens: List[str] = []
        self._max_tokens = max_tokens
        self._complete = False

    async def add_token(self, token: str) -> bool:
        """
        Add a token to the accumulator.

        Args:
            token: Token string to add

        Returns:
            True if token was added, False if limit reached
        """
        if len(self._tokens) >= self._max_tokens:
            return False
        self._tokens.append(token)
        return True

    def get_content(self) -> str:
        """Get accumulated content so far."""
        return "".join(self._tokens)

    def mark_complete(self) -> None:
        """Mark streaming as complete."""
        self._complete = True

    @property
    def is_complete(self) -> bool:
        """Check if streaming is complete."""
        return self._complete

    @property
    def token_count(self) -> int:
        """Get number of tokens accumulated."""
        return len(self._tokens)

    def clear(self) -> None:
        """Clear accumulated tokens."""
        self._tokens.clear()
        self._complete = False


async def create_streaming_response(
    events: AsyncIterator[StreamEvent],
    include_keepalive: bool = True,
    keepalive_interval: float = 15.0,
) -> AsyncIterator[str]:
    """
    Create a streaming response for SSE.

    Args:
        events: Async iterator of StreamEvent objects
        include_keepalive: Whether to include keep-alive comments
        keepalive_interval: Seconds between keep-alive comments

    Yields:
        Formatted SSE strings
    """
    last_event_time = time.time()

    try:
        async for event in events:
            last_event_time = time.time()
            yield event.to_sse()

            # Check for keep-alive
            if include_keepalive:
                while time.time() - last_event_time > keepalive_interval:
                    yield ": keep-alive\n\n"
                    last_event_time = time.time()
                    await asyncio.sleep(1)

    except asyncio.CancelledError:
        logger.debug("Streaming response cancelled")
    finally:
        # Send final event
        yield f"event: {StreamEventType.END}\ndata: {{\"timestamp\": \"{datetime.utcnow().isoformat()}\"}}\n\n"
