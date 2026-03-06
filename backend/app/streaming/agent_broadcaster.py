"""
Agent Status Broadcaster

Broadcasts real-time agent state changes to connected clients.
Integrates with the BaseAgent to automatically publish status updates.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ..agents.base_agent import BaseAgent, AgentState, AgentRole
from .connection_manager import ConnectionManager, get_connection_manager

logger = logging.getLogger(__name__)


@dataclass
class AgentStatusUpdate:
    """Agent status update for broadcasting."""
    agent_id: str
    agent_role: AgentRole
    state: AgentState
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role.value,
            "state": self.state.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "progress": self.progress,
            "metadata": self.metadata,
        }


class AgentStatusBroadcaster:
    """
    Manages broadcasting of agent status updates.

    Features:
    - Automatic status tracking for registered agents
    - Filtered broadcasting by agent or session
    - Progress tracking
    - Event-driven updates
    """

    def __init__(
        self,
        connection_manager: Optional[ConnectionManager] = None,
    ):
        """
        Initialize the broadcaster.

        Args:
            connection_manager: Optional custom connection manager
        """
        self.connection_manager = connection_manager or get_connection_manager()
        self._registered_agents: Dict[str, BaseAgent] = {}
        self._agent_states: Dict[str, AgentState] = {}
        self._agent_progress: Dict[str, float] = {}
        self._subscribers: Dict[str, Set[str]] = {}  # agent_id -> set of session_ids
        self._status_callbacks: List[Callable[[AgentStatusUpdate], Any]] = []
        self._lock = asyncio.Lock()

    async def register_agent(self, agent: BaseAgent) -> None:
        """
        Register an agent for status broadcasting.

        Args:
            agent: The agent to register
        """
        async with self._lock:
            self._registered_agents[agent.config.name] = agent
            self._agent_states[agent.config.name] = agent.state
            self._subscribers[agent.config.name] = set()

        logger.info(f"Registered agent for broadcasting: {agent.config.name}")

    async def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister an agent from broadcasting.

        Args:
            agent_id: The agent identifier
        """
        async with self._lock:
            self._registered_agents.pop(agent_id, None)
            self._agent_states.pop(agent_id, None)
            self._agent_progress.pop(agent_id, None)
            self._subscribers.pop(agent_id, None)

        logger.info(f"Unregistered agent: {agent_id}")

    async def subscribe(
        self,
        session_id: str,
        agent_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Subscribe a session to agent status updates.

        Args:
            session_id: Session identifier
            agent_ids: Optional list of specific agents to subscribe to
        """
        async with self._lock:
            if agent_ids:
                for agent_id in agent_ids:
                    if agent_id in self._subscribers:
                        self._subscribers[agent_id].add(session_id)
            else:
                # Subscribe to all agents
                for agent_id in self._subscribers:
                    self._subscribers[agent_id].add(session_id)

        logger.info(f"Session {session_id} subscribed to agent updates")

    async def unsubscribe(self, session_id: str, agent_id: Optional[str] = None) -> None:
        """
        Unsubscribe a session from agent status updates.

        Args:
            session_id: Session identifier
            agent_id: Optional specific agent to unsubscribe from
        """
        async with self._lock:
            if agent_id:
                if agent_id in self._subscribers:
                    self._subscribers[agent_id].discard(session_id)
            else:
                # Unsubscribe from all agents
                for agent_subscribers in self._subscribers.values():
                    agent_subscribers.discard(session_id)

    async def broadcast_status(
        self,
        agent_id: str,
        state: AgentState,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Broadcast an agent status update.

        Args:
            agent_id: Agent identifier
            state: Current agent state
            message: Optional status message
            progress: Optional progress value (0.0 to 1.0)
            metadata: Optional additional metadata

        Returns:
            Number of clients the update was sent to
        """
        # Get agent role
        agent = self._registered_agents.get(agent_id)
        role = agent.config.role if agent else AgentRole.CHAT_ORCHESTRATOR

        # Update internal state
        async with self._lock:
            self._agent_states[agent_id] = state
            if progress is not None:
                self._agent_progress[agent_id] = progress

        # Create status update
        update = AgentStatusUpdate(
            agent_id=agent_id,
            agent_role=role,
            state=state,
            message=message,
            progress=progress or self._agent_progress.get(agent_id, 0.0),
            metadata=metadata or {},
        )

        # Call registered callbacks
        for callback in self._status_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

        # Broadcast to subscribed sessions
        target_sessions = self._subscribers.get(agent_id, set())

        sent_count = 0
        for session_id in target_sessions:
            count = await self.connection_manager.broadcast(
                data=update.to_dict(),
                event_type="agent_status",
                session_id=session_id,
                agent_id=agent_id,
            )
            sent_count += count

        return sent_count

    async def broadcast_progress(
        self,
        agent_id: str,
        stage: str,
        message: str,
        progress_percent: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Broadcast a progress update for an agent.

        Args:
            agent_id: Agent identifier
            stage: Current processing stage
            message: Human-readable progress message
            progress_percent: Progress from 0.0 to 1.0
            metadata: Optional additional metadata

        Returns:
            Number of clients the update was sent to
        """
        return await self.broadcast_status(
            agent_id=agent_id,
            state=AgentState.EXECUTING,
            message=f"[{stage}] {message}",
            progress=progress_percent,
            metadata={
                "stage": stage,
                **(metadata or {}),
            },
        )

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent status dict or None if not found
        """
        agent = self._registered_agents.get(agent_id)
        if not agent:
            return None

        return {
            "agent_id": agent_id,
            "agent_role": agent.config.role.value,
            "state": agent.state.value,
            "progress": self._agent_progress.get(agent_id, 0.0),
            "subscribers": len(self._subscribers.get(agent_id, set())),
        }

    async def get_all_statuses(self) -> List[Dict[str, Any]]:
        """Get status of all registered agents."""
        statuses = []
        for agent_id in self._registered_agents:
            status = await self.get_agent_status(agent_id)
            if status:
                statuses.append(status)
        return statuses

    def add_status_callback(self, callback: Callable[[AgentStatusUpdate], Any]) -> None:
        """
        Add a callback to be called on every status update.

        Args:
            callback: Function to call with AgentStatusUpdate
        """
        self._status_callbacks.append(callback)

    def remove_status_callback(self, callback: Callable[[AgentStatusUpdate], Any]) -> None:
        """
        Remove a status callback.

        Args:
            callback: Previously registered callback function
        """
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)


class AgentInstrumentation:
    """
    Instrumentation wrapper for agents to automatically broadcast status.

    Wraps an agent and broadcasts status changes during execution.
    """

    def __init__(
        self,
        agent: BaseAgent,
        broadcaster: Optional[AgentStatusBroadcaster] = None,
    ):
        """
        Initialize instrumentation.

        Args:
            agent: The agent to instrument
            broadcaster: Optional custom broadcaster
        """
        self.agent = agent
        self.broadcaster = broadcaster or AgentStatusBroadcaster()
        self._original_execute = agent.execute

        # Register agent with broadcaster
        asyncio.create_task(self.broadcaster.register_agent(agent))

    async def instrumented_execute(
        self,
        input_data: Any,
        context: Any,
    ) -> Any:
        """
        Execute agent with automatic status broadcasting.

        Args:
            input_data: Input data for agent
            context: Agent context

        Returns:
            Agent response
        """
        agent_id = self.agent.config.name

        try:
            # Broadcast start
            await self.broadcaster.broadcast_status(
                agent_id=agent_id,
                state=AgentState.THINKING,
                message="Starting processing...",
                progress=0.0,
            )

            # Execute original method
            response = await self._original_execute(input_data, context)

            # Broadcast completion
            await self.broadcaster.broadcast_status(
                agent_id=agent_id,
                state=AgentState.COMPLETED,
                message="Processing complete",
                progress=1.0,
                metadata={"response_length": len(response.content) if response.content else 0},
            )

            return response

        except Exception as e:
            # Broadcast error
            await self.broadcaster.broadcast_status(
                agent_id=agent_id,
                state=AgentState.FAILED,
                message=f"Error: {str(e)}",
                metadata={"error_type": type(e).__name__},
            )
            raise

    def apply_instrumentation(self) -> None:
        """Apply instrumentation to the agent."""
        self.agent.execute = self.instrumented_execute


# Global broadcaster instance
_broadcaster: Optional[AgentStatusBroadcaster] = None


def get_broadcaster() -> AgentStatusBroadcaster:
    """Get the global broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = AgentStatusBroadcaster()
    return _broadcaster


async def broadcast_agent_status(
    agent_id: str,
    state: AgentState,
    message: Optional[str] = None,
    progress: Optional[float] = None,
) -> int:
    """
    Convenience function to broadcast agent status.

    Args:
        agent_id: Agent identifier
        state: Current agent state
        message: Optional status message
        progress: Optional progress value

    Returns:
        Number of clients the update was sent to
    """
    broadcaster = get_broadcaster()
    return await broadcaster.broadcast_status(
        agent_id=agent_id,
        state=state,
        message=message,
        progress=progress,
    )
