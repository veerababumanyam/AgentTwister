"""
Agent Registry

Central registry for managing agent instances and their configurations.
Provides agent discovery, lifecycle management, and health monitoring.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from .base_agent import BaseAgent, AgentConfig, AgentRole
from .a2a import A2AProtocolAdapter, A2AConfig

logger = logging.getLogger(__name__)


class AgentLifecycleState(Enum):
    """Agent lifecycle states."""
    REGISTERED = "registered"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentRecord:
    """Record of a registered agent."""
    agent: BaseAgent
    state: AgentLifecycleState = AgentLifecycleState.REGISTERED
    started_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    health_status: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_running(self) -> bool:
        """Check if agent is running."""
        return self.state == AgentLifecycleState.RUNNING

    @property
    def uptime_seconds(self) -> Optional[float]:
        """Get agent uptime in seconds."""
        if self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return None


class AgentRegistry:
    """
    Central registry for agent management.

    Provides:
    - Agent registration and lookup
    - Lifecycle management (start/stop agents)
    - Health monitoring
    - Service discovery integration
    """

    _instance: Optional["AgentRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._agents: Dict[str, AgentRecord] = {}
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._health_check_interval = 30.0  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._initialized = True

        logger.info("AgentRegistry initialized")

    def register_class(
        self,
        name: str,
        agent_class: Type[BaseAgent],
    ) -> None:
        """
        Register an agent class for instantiation.

        Args:
            name: Name/key for the agent class
            agent_class: Agent class to register
        """
        self._agent_classes[name] = agent_class
        logger.info(f"Registered agent class: {name}")

    def register_agent(
        self,
        name: str,
        agent: BaseAgent,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentRecord:
        """
        Register an agent instance.

        Args:
            name: Unique name for the agent
            agent: Agent instance
            metadata: Optional metadata

        Returns:
            Agent record
        """
        if name in self._agents:
            logger.warning(f"Agent '{name}' already registered, replacing")

        record = AgentRecord(
            agent=agent,
            metadata=metadata or {},
        )
        self._agents[name] = record
        logger.info(f"Registered agent instance: {name} (role: {agent.config.role.value})")

        return record

    def unregister(self, name: str) -> Optional[AgentRecord]:
        """
        Unregister an agent.

        Args:
            name: Agent name

        Returns:
            Removed record or None
        """
        record = self._agents.pop(name, None)
        if record:
            logger.info(f"Unregistered agent: {name}")
        return record

    def get(self, name: str) -> Optional[BaseAgent]:
        """
        Get an agent by name.

        Args:
            name: Agent name

        Returns:
            Agent instance or None
        """
        record = self._agents.get(name)
        return record.agent if record else None

    def get_record(self, name: str) -> Optional[AgentRecord]:
        """Get agent record by name."""
        return self._agents.get(name)

    def list_agents(
        self,
        role: Optional[AgentRole] = None,
        state: Optional[AgentLifecycleState] = None,
    ) -> List[AgentRecord]:
        """
        List registered agents with optional filtering.

        Args:
            role: Filter by agent role
            state: Filter by lifecycle state

        Returns:
            List of agent records
        """
        agents = list(self._agents.values())

        if role:
            agents = [a for a in agents if a.agent.config.role == role]

        if state:
            agents = [a for a in agents if a.state == state]

        return agents

    def get_by_role(self, role: AgentRole) -> List[BaseAgent]:
        """Get all agents of a specific role."""
        return [
            record.agent
            for record in self.list_agents(role=role)
        ]

    async def start_agent(self, name: str) -> bool:
        """
        Start an agent.

        Args:
            name: Agent name

        Returns:
            True if started successfully
        """
        record = self.get_record(name)
        if not record:
            logger.error(f"Cannot start unknown agent: {name}")
            return False

        if record.is_running:
            logger.warning(f"Agent '{name}' already running")
            return True

        record.state = AgentLifecycleState.STARTING

        try:
            # Perform agent initialization
            # (Agents can override this behavior)
            await record.agent.execute("", None)  # Dummy execution to test

            record.state = AgentLifecycleState.RUNNING
            record.started_at = datetime.utcnow()
            logger.info(f"Agent '{name}' started")
            return True

        except Exception as e:
            record.state = AgentLifecycleState.ERROR
            logger.error(f"Failed to start agent '{name}': {e}")
            return False

    async def stop_agent(self, name: str) -> bool:
        """
        Stop an agent.

        Args:
            name: Agent name

        Returns:
            True if stopped successfully
        """
        record = self.get_record(name)
        if not record:
            return False

        record.state = AgentLifecycleState.STOPPING
        record.state = AgentLifecycleState.STOPPED
        logger.info(f"Agent '{name}' stopped")
        return True

    async def start_all(self) -> Dict[str, bool]:
        """
        Start all registered agents.

        Returns:
            Dict mapping agent names to start success
        """
        results = {}
        for name in self._agents:
            results[name] = await self.start_agent(name)
        return results

    async def stop_all(self) -> Dict[str, bool]:
        """
        Stop all registered agents.

        Returns:
            Dict mapping agent names to stop success
        """
        results = {}
        for name in self._agents:
            results[name] = await self.stop_agent(name)
        return results

    async def health_check(self, name: str) -> bool:
        """
        Perform health check on an agent.

        Args:
            name: Agent name

        Returns:
            True if agent is healthy
        """
        record = self.get_record(name)
        if not record:
            return False

        record.last_health_check = datetime.utcnow()

        # Check if agent is in running state
        if not record.is_running:
            record.health_status = "not_running"
            return False

        # Agent-specific health check could go here
        # For now, just check state
        record.health_status = "healthy"
        return True

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Perform health check on all agents.

        Returns:
            Dict mapping agent names to health status
        """
        results = {}
        for name in self._agents:
            results[name] = await self.health_check(name)
        return results

    async def start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._health_check_task and not self._health_check_task.done():
            return

        async def _monitor():
            while True:
                try:
                    await self.health_check_all()
                    await asyncio.sleep(self._health_check_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")

        self._health_check_task = asyncio.create_task(_monitor())
        logger.info("Health monitoring started")

    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None
            logger.info("Health monitoring stopped")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Stats dict with agent counts and states
        """
        total = len(self._agents)
        by_state: Dict[str, int] = {}
        by_role: Dict[str, int] = {}

        for record in self._agents.values():
            # Count by state
            state_name = record.state.value
            by_state[state_name] = by_state.get(state_name, 0) + 1

            # Count by role
            role_name = record.agent.config.role.value
            by_role[role_name] = by_role.get(role_name, 0) + 1

        return {
            "total_agents": total,
            "by_state": by_state,
            "by_role": by_role,
            "health_check_interval": self._health_check_interval,
        }


def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    return AgentRegistry()


# ============================================================
# AGENT FACTORY
# ============================================================

class AgentFactory:
    """
    Factory for creating agent instances from configurations.

    Provides a centralized way to instantiate agents with
    proper configuration and tool binding.
    """

    def __init__(self, registry: Optional[AgentRegistry] = None):
        """
        Initialize factory.

        Args:
            registry: Agent registry (uses global if None)
        """
        self.registry = registry or get_registry()

    def create_agent(
        self,
        agent_class: Type[BaseAgent],
        name: str,
        role: AgentRole,
        model_alias: str = "gpt-4o-primary",
        **config_kwargs,
    ) -> BaseAgent:
        """
        Create and configure an agent instance.

        Args:
            agent_class: Agent class to instantiate
            name: Agent name
            role: Agent role
            model_alias: LiteLLM model alias
            **config_kwargs: Additional config parameters

        Returns:
            Configured agent instance
        """
        from .tools import ToolFactory

        # Create agent configuration
        config = AgentConfig(
            name=name,
            role=role,
            model_alias=model_alias,
            **config_kwargs,
        )

        # Create tools for the agent
        tools = []

        # All agents get basic tools
        tools.append(ToolFactory.get_file_parser().to_definition())
        tools.append(ToolFactory.get_database_reader().to_definition())
        tools.append(ToolFactory.get_database_writer().to_definition())

        # Add HTTP tool for most agents
        if role not in (AgentRole.REVIEWER, AgentRole.FORMATTER):
            tools.append(ToolFactory.get_http_caller().to_definition())

        # Create agent instance
        agent = agent_class(config=config, tools=tools)

        logger.info(f"Created agent: {name} (role: {role.value})")
        return agent

    def create_and_register(
        self,
        agent_class: Type[BaseAgent],
        name: str,
        role: AgentRole,
        **kwargs,
    ) -> BaseAgent:
        """
        Create agent and register it.

        Args:
            agent_class: Agent class
            name: Agent name
            role: Agent role
            **kwargs: Additional config

        Returns:
            Agent instance
        """
        agent = self.create_agent(agent_class, name, role, **kwargs)
        self.registry.register_agent(name, agent)
        return agent
