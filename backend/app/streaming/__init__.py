"""
Streaming Adapter Module

Provides real-time agent status and progress updates via WebSocket and SSE.
Implements token-level streaming with <500ms time-to-first-token latency.

Architecture:
- ConnectionManager: Manages WebSocket and SSE connections
- StreamingAdapter: Unified interface for both protocols
- AgentStatusBroadcaster: Broadcasts agent state changes
"""

from .connection_manager import (
    ConnectionManager,
    ConnectionType,
    get_connection_manager,
)
from .streaming_adapter import (
    StreamingAdapter,
    StreamEvent,
    StreamEventType,
    create_streaming_response,
)
from .agent_broadcaster import (
    AgentStatusBroadcaster,
    broadcast_agent_status,
    get_broadcaster,
)

__all__ = [
    "ConnectionManager",
    "ConnectionType",
    "get_connection_manager",
    "StreamingAdapter",
    "StreamEvent",
    "StreamEventType",
    "create_streaming_response",
    "AgentStatusBroadcaster",
    "broadcast_agent_status",
    "get_broadcaster",
]
