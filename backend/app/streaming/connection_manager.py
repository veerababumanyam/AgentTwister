"""
Connection Manager for WebSocket and SSE

Manages persistent connections for real-time streaming.
Supports both WebSocket (bidirectional) and SSE (unidirectional) connections.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, Optional, Set

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


class ConnectionType(Enum):
    """Type of streaming connection."""
    WEBSOCKET = "websocket"
    SSE = "sse"


@dataclass
class Connection:
    """A single streaming connection."""
    connection_id: str
    connection_type: ConnectionType
    session_id: str
    websocket: Optional[WebSocket] = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    # Filters for selective broadcasting
    subscribed_events: Set[str] = field(default_factory=set)
    subscribed_agents: Set[str] = field(default_factory=set)

    async def send(self, data: Dict[str, Any]) -> bool:
        """Send data to this connection."""
        try:
            if self.connection_type == ConnectionType.WEBSOCKET and self.websocket:
                await self.websocket.send_json(data)
                return True
            else:
                # For SSE, put in queue
                await self.queue.put(data)
                return True
        except Exception as e:
            logger.warning(f"Failed to send to connection {self.connection_id}: {e}")
            return False

    def is_subscribed(self, event_type: str, agent_id: Optional[str] = None) -> bool:
        """Check if connection is subscribed to this event."""
        if self.subscribed_events and event_type not in self.subscribed_events:
            return False
        if agent_id and self.subscribed_agents and agent_id not in self.subscribed_agents:
            return False
        return True


class ConnectionManager:
    """
    Manages all WebSocket and SSE connections.

    Features:
    - Connection lifecycle management
    - Broadcast to all or filtered connections
    - Heartbeat/ping monitoring
    - Session-based grouping
    """

    def __init__(self, ping_interval: float = 30.0, ping_timeout: float = 60.0):
        """
        Initialize the connection manager.

        Args:
            ping_interval: Seconds between ping frames
            ping_timeout: Seconds before closing unresponsive connection
        """
        self._connections: Dict[str, Connection] = {}
        self._session_connections: Dict[str, Set[str]] = {}  # session_id -> connection_ids
        self._ping_interval = ping_interval
        self._ping_timeout = ping_timeout
        self._ping_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def _ping_loop(self):
        """Background task to send pings and cleanup dead connections."""
        while True:
            try:
                await asyncio.sleep(self._ping_interval)
                await self._send_pings()
                await self._cleanup_stale()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in ping loop: {e}", exc_info=True)

    async def _send_pings(self):
        """Send ping to all WebSocket connections."""
        now = datetime.utcnow()
        to_remove = []

        async with self._lock:
            for conn_id, conn in self._connections.items():
                if conn.connection_type == ConnectionType.WEBSOCKET and conn.websocket:
                    try:
                        await conn.websocket.send_json({"type": "ping", "timestamp": now.isoformat()})
                        conn.last_ping = now
                    except Exception:
                        to_remove.append(conn_id)

        for conn_id in to_remove:
            await self.disconnect(conn_id)

    async def _cleanup_stale(self):
        """Remove connections that haven't responded to ping."""
        now = datetime.utcnow()
        to_remove = []

        async with self._lock:
            for conn_id, conn in self._connections.items():
                stale_time = (now - conn.last_ping).total_seconds()
                if stale_time > self._ping_timeout:
                    logger.info(f"Cleaning up stale connection {conn_id}")
                    to_remove.append(conn_id)

        for conn_id in to_remove:
            await self.disconnect(conn_id)

    def _start_ping_loop(self):
        """Start the background ping task if not running."""
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = asyncio.create_task(self._ping_loop())

    async def connect_websocket(
        self,
        websocket: WebSocket,
        session_id: str,
        subscribed_events: Optional[Set[str]] = None,
        subscribed_agents: Optional[Set[str]] = None,
    ) -> Connection:
        """
        Accept and register a WebSocket connection.

        Args:
            websocket: The WebSocket connection
            session_id: Session identifier
            subscribed_events: Event types to subscribe to
            subscribed_agents: Specific agents to subscribe to

        Returns:
            The created Connection object
        """
        await websocket.accept()
        self._start_ping_loop()

        conn_id = str(uuid.uuid4())
        connection = Connection(
            connection_id=conn_id,
            connection_type=ConnectionType.WEBSOCKET,
            session_id=session_id,
            websocket=websocket,
            subscribed_events=subscribed_events or set(),
            subscribed_agents=subscribed_agents or set(),
        )

        async with self._lock:
            self._connections[conn_id] = connection
            if session_id not in self._session_connections:
                self._session_connections[session_id] = set()
            self._session_connections[session_id].add(conn_id)

        logger.info(f"WebSocket connected: {conn_id} (session: {session_id})")

        # Send welcome message
        await connection.send({
            "type": "connected",
            "connection_id": conn_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return connection

    async def connect_sse(
        self,
        session_id: str,
        subscribed_events: Optional[Set[str]] = None,
        subscribed_agents: Optional[Set[str]] = None,
    ) -> Connection:
        """
        Create an SSE connection (returns Connection with queue).

        Args:
            session_id: Session identifier
            subscribed_events: Event types to subscribe to
            subscribed_agents: Specific agents to subscribe to

        Returns:
            The created Connection object
        """
        self._start_ping_loop()

        conn_id = str(uuid.uuid4())
        connection = Connection(
            connection_id=conn_id,
            connection_type=ConnectionType.SSE,
            session_id=session_id,
            subscribed_events=subscribed_events or set(),
            subscribed_agents=subscribed_agents or set(),
        )

        async with self._lock:
            self._connections[conn_id] = connection
            if session_id not in self._session_connections:
                self._session_connections[session_id] = set()
            self._session_connections[session_id].add(conn_id)

        logger.info(f"SSE connection created: {conn_id} (session: {session_id})")

        return connection

    async def disconnect(self, connection_id: str) -> bool:
        """
        Remove a connection.

        Args:
            connection_id: The connection ID to remove

        Returns:
            True if connection was removed
        """
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            if connection:
                # Remove from session mapping
                if connection.session_id in self._session_connections:
                    self._session_connections[connection.session_id].discard(connection_id)
                    if not self._session_connections[connection.session_id]:
                        del self._session_connections[connection.session_id]

                # Close WebSocket if applicable
                if connection.websocket:
                    try:
                        await connection.websocket.close()
                    except Exception:
                        pass

                logger.info(f"Disconnected: {connection_id}")
                return True
        return False

    async def broadcast(
        self,
        data: Dict[str, Any],
        event_type: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        exclude_connection: Optional[str] = None,
    ) -> int:
        """
        Broadcast data to connections.

        Args:
            data: Data to broadcast
            event_type: Type of event (for filtering)
            session_id: Optional session ID to target only that session
            agent_id: Optional agent ID for agent-specific events
            exclude_connection: Connection ID to exclude

        Returns:
            Number of connections the data was sent to
        """
        # Create event envelope
        event_data = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        sent_count = 0
        failed_connections = []

        async with self._lock:
            # Determine target connections
            if session_id:
                target_ids = self._session_connections.get(session_id, set())
            else:
                target_ids = set(self._connections.keys())

            for conn_id in target_ids:
                if conn_id == exclude_connection:
                    continue

                conn = self._connections.get(conn_id)
                if not conn:
                    continue

                # Check subscription filters
                if not conn.is_subscribed(event_type, agent_id):
                    continue

                # Send asynchronously without blocking
                try:
                    success = await conn.send(event_data)
                    if success:
                        sent_count += 1
                    else:
                        failed_connections.append(conn_id)
                except Exception as e:
                    logger.warning(f"Failed to broadcast to {conn_id}: {e}")
                    failed_connections.append(conn_id)

        # Cleanup failed connections
        for conn_id in failed_connections:
            await self.disconnect(conn_id)

        return sent_count

    async def get_session_connections(self, session_id: str) -> list[Connection]:
        """Get all connections for a session."""
        async with self._lock:
            conn_ids = self._session_connections.get(session_id, set())
            return [self._connections.get(cid) for cid in conn_ids if cid in self._connections]

    async def iter_sse_events(self, connection: Connection) -> AsyncIterator[str]:
        """
        Iterate over SSE events for a connection.

        Yields formatted SSE strings.
        """
        try:
            while True:
                try:
                    # Wait for event with timeout
                    data = await asyncio.wait_for(
                        connection.queue.get(),
                        timeout=1.0,
                    )
                    # Format as SSE
                    yield f"event: {data.get('type', 'message')}\ndata: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    # Send keep-alive comment
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            logger.debug(f"SSE iteration cancelled for {connection.connection_id}")

    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self._connections)

    @property
    def session_count(self) -> int:
        """Get number of unique sessions."""
        return len(self._session_connections)


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
