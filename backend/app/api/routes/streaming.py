"""
Streaming API Routes

Provides WebSocket and SSE endpoints for real-time agent status
and token-level streaming responses.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ...streaming import (
    ConnectionManager,
    ConnectionType,
    StreamEvent,
    StreamEventType,
    StreamingAdapter,
    get_connection_manager,
    create_streaming_response,
)
from ...streaming.agent_broadcaster import (
    AgentStatusBroadcaster,
    broadcast_agent_status,
    get_broadcaster,
)
from ...agents import ChatOrchestratorAgent, AgentContext
from ...agents.registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/streaming",
    tags=["Streaming"],
    responses={404: {"description": "Not found"}},
)


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class StreamSubscribeRequest(BaseModel):
    """Request to subscribe to streaming events."""

    events: Optional[List[str]] = Field(
        None,
        description="Event types to subscribe to (empty = all)",
    )
    agents: Optional[List[str]] = Field(
        None,
        description="Agent IDs to subscribe to (empty = all)",
    )


class StreamStatusResponse(BaseModel):
    """Response for stream status queries."""

    active_connections: int
    active_sessions: int
    connected_agents: List[str]
    uptime_seconds: float


class TokenStreamRequest(BaseModel):
    """Request for token-level streaming."""

    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(None, description="Session ID for continuity")
    agent_id: Optional[str] = Field(None, description="Specific agent to use")


# ============================================================
# DEPENDENCIES
# ============================================================

def get_connection_manager_dep() -> ConnectionManager:
    """Get connection manager dependency."""
    return get_connection_manager()


def get_broadcaster_dep() -> AgentStatusBroadcaster:
    """Get broadcaster dependency."""
    return get_broadcaster()


async def get_chat_orchestrator() -> ChatOrchestratorAgent:
    """Get or create the Chat Orchestrator agent instance."""
    registry = get_registry()
    agent = registry.get("chat_orchestrator")

    if not agent:
        from ...agents import create_chat_orchestrator_agent
        agent = create_chat_orchestrator_agent()
        registry.register_agent("chat_orchestrator", agent)

    return agent


# ============================================================
# WEBSOCKET ENDPOINT
# ============================================================

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = Query(None),
    manager: ConnectionManager = Depends(get_connection_manager_dep),
):
    """
    WebSocket endpoint for real-time bidirectional streaming.

    Connect with: ws://localhost:8000/api/v1/streaming/ws?session_id=xxx

    Client protocol:
    - Send JSON messages to configure or interact
    - Receive JSON events for agent status and tokens

    Example client message:
        {"type": "subscribe", "events": ["token", "agent_status"], "agents": ["chat_orchestrator"]}

    Server events:
        - connected: Connection established
        - token: Token from LLM stream
        - agent_status: Agent state change
        - progress: Progress update
        - error: Error occurred
        - ping: Keep-alive
    """
    session_id = session_id or str(uuid.uuid4())

    try:
        # Accept and register connection
        connection = await manager.connect_websocket(
            websocket=websocket,
            session_id=session_id,
        )

        logger.info(f"WebSocket connected: {connection.connection_id} (session: {session_id})")

        # Handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)

                msg_type = message.get("type")

                if msg_type == "subscribe":
                    # Update subscriptions
                    events = set(message.get("events", []))
                    agents = set(message.get("agents", []))
                    connection.subscribed_events = events
                    connection.subscribed_agents = agents

                    await connection.send({
                        "type": "subscribed",
                        "events": list(events),
                        "agents": list(agents),
                    })

                elif msg_type == "ping":
                    # Respond to ping
                    await connection.send({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                elif msg_type == "chat":
                    # Handle chat message
                    message_content = message.get("message", "")
                    if message_content:
                        # Process and stream response
                        orchestrator = await get_chat_orchestrator()
                        context = AgentContext(
                            session_id=session_id,
                            messages=[],
                        )

                        # Send acknowledgment
                        await connection.send({
                            "type": "chat_ack",
                            "message_id": message.get("id"),
                        })

                        # Stream the response
                        async for response in orchestrator.process_with_streaming(
                            context=context,
                            message=message_content,
                        ):
                            await connection.send({
                                "type": "chat_progress",
                                "stage": response.stage,
                                "message": response.message,
                                "progress": response.progress_percent,
                            })

                else:
                    await connection.send({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })

            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection.connection_id}")
                break
            except json.JSONDecodeError:
                await connection.send({
                    "type": "error",
                    "message": "Invalid JSON",
                })
            except Exception as e:
                logger.error(f"WebSocket message error: {e}", exc_info=True)
                await connection.send({
                    "type": "error",
                    "message": str(e),
                })

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        await manager.disconnect(connection.connection_id)


# ============================================================
# SSE ENDPOINTS
# ============================================================

@router.get("/sse")
async def sse_endpoint(
    message: str = Query(..., description="Message to stream response for"),
    session_id: Optional[str] = Query(None, description="Session ID for continuity"),
    events: Optional[str] = Query(None, description="Comma-separated event types"),
    agents: Optional[str] = Query(None, description="Comma-separated agent IDs"),
    manager: ConnectionManager = Depends(get_connection_manager_dep),
):
    """
    SSE endpoint for unidirectional streaming.

    Connect to: GET /api/v1/streaming/sse?message=Hello&events=token,agent_status

    Returns Server-Sent Events for:
    - token: Token-level LLM responses
    - agent_status: Agent state changes
    - progress: Progress updates
    - error: Errors
    """
    session_id = session_id or str(uuid.uuid4())

    # Parse subscription filters
    subscribed_events = set(events.split(",")) if events else None
    subscribed_agents = set(agents.split(",")) if agents else None

    # Create SSE connection
    connection = await manager.connect_sse(
        session_id=session_id,
        subscribed_events=subscribed_events,
        subscribed_agents=subscribed_agents,
    )

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events."""
        try:
            # Send initial connected event
            yield f"event: connected\ndata: {json.dumps({'session_id': session_id, 'connection_id': connection.connection_id})}\n\n"

            # Process the message and stream response
            orchestrator = await get_chat_orchestrator()
            context = AgentContext(
                session_id=session_id,
                messages=[],
            )

            # Create streaming adapter
            adapter = StreamingAdapter(
                agent=orchestrator,
                connection_manager=manager,
            )

            # Stream LLM response token by token
            async for event in adapter.stream_llm_response(
                prompt=message,
                context=context,
                session_id=session_id,
            ):
                # Check subscription
                event_type = event.event_type.value if isinstance(event.event_type, StreamEventType) else event.event_type
                if subscribed_events and event_type not in subscribed_events:
                    continue
                if subscribed_agents and event.agent_id and event.agent_id not in subscribed_agents:
                    continue

                yield event.to_sse()

            # Send done event
            yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

        except Exception as e:
            logger.error(f"SSE error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status")
async def get_streaming_status(
    manager: ConnectionManager = Depends(get_connection_manager_dep),
    broadcaster: AgentStatusBroadcaster = Depends(get_broadcaster_dep),
):
    """
    Get streaming system status.

    Returns information about active connections and agents.
    """
    agent_statuses = await broadcaster.get_all_statuses()

    return {
        "success": True,
        "connections": {
            "active": manager.connection_count,
            "sessions": manager.session_count,
        },
        "agents": agent_statuses,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/agents/{agent_id}/status")
async def get_agent_status(
    agent_id: str,
    broadcaster: AgentStatusBroadcaster = Depends(get_broadcaster_dep),
):
    """
    Get status of a specific agent.

    Args:
        agent_id: Agent identifier

    Returns current agent state and progress.
    """
    status = await broadcaster.get_agent_status(agent_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Agent '{agent_id}' not found"},
        )

    return {
        "success": True,
        "status": status,
    }


# ============================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================

@router.post("/subscribe")
async def subscribe_to_events(
    subscription: StreamSubscribeRequest,
    session_id: str = Query(..., description="Session ID"),
    broadcaster: AgentStatusBroadcaster = Depends(get_broadcaster_dep),
):
    """
    Subscribe a session to specific events and agents.

    Use this to configure what events a session receives.
    """
    await broadcaster.subscribe(
        session_id=session_id,
        agent_ids=subscription.agents,
    )

    return {
        "success": True,
        "session_id": session_id,
        "subscribed_events": subscription.events or ["all"],
        "subscribed_agents": subscription.agents or ["all"],
    }


@router.post("/unsubscribe")
async def unsubscribe_from_events(
    subscription: StreamSubscribeRequest,
    session_id: str = Query(..., description="Session ID"),
    broadcaster: AgentStatusBroadcaster = Depends(get_broadcaster_dep),
):
    """
    Unsubscribe a session from specific events or agents.
    """
    await broadcaster.unsubscribe(
        session_id=session_id,
        agent_id=subscription.agents[0] if subscription.agents else None,
    )

    return {
        "success": True,
        "session_id": session_id,
        "message": "Unsubscribed",
    }


# ============================================================
# TOKEN STREAMING ENDPOINT
# ============================================================

@router.post("/tokens")
async def stream_tokens(
    request: TokenStreamRequest,
    manager: ConnectionManager = Depends(get_connection_manager_dep),
):
    """
    Stream LLM responses token-by-token.

    Provides <500ms time-to-first-token latency.

    Events:
        - token_start: First token (includes TTFM metric)
        - token: Subsequent tokens
        - token_end: Stream completion with metrics
        - error: If streaming fails
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def token_stream() -> AsyncIterator[str]:
        """Generate token stream events."""
        try:
            # Send start event
            start_event = {
                "type": "stream_start",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: start\ndata: {json.dumps(start_event)}\n\n"

            # Get orchestrator and stream
            orchestrator = await get_chat_orchestrator()
            context = AgentContext(
                session_id=session_id,
                messages=[],
            )

            adapter = StreamingAdapter(
                agent=orchestrator,
                connection_manager=manager,
            )

            async for event in adapter.stream_llm_response(
                prompt=request.message,
                context=context,
                session_id=session_id,
            ):
                yield event.to_sse()

        except Exception as e:
            logger.error(f"Token stream error: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
