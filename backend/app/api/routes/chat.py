"""
Chat API Routes

FastAPI endpoints for the Chat Orchestrator agent.
These routes provide the primary entry point for user interactions with AgentTwister.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents import (
    ChatOrchestratorAgent,
    create_chat_orchestrator_agent,
    AgentContext,
    UserIntent as AgentUserIntent,
    StreamingProgress,
)
from app.agents.registry import get_registry
from app.models.chat import (
    UserIntent,
    IntentConfidence,
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    ProgressUpdate,
    IntentClassification,
    ClarificationResponse,
    ConversationHistory,
    ConversationSummary,
    AgentCapabilities,
    HealthStatus,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
    responses={404: {"description": "Not found"}},
)


# ============================================================
# DEPENDENCIES
# ============================================================

# Session storage (in production, use Redis or similar)
_session_storage: Dict[str, ConversationHistory] = {}


def get_session(session_id: Optional[str]) -> ConversationHistory:
    """Get or create a conversation session."""
    if not session_id:
        session_id = str(uuid.uuid4())

    if session_id not in _session_storage:
        _session_storage[session_id] = ConversationHistory(session_id=session_id)

    return _session_storage[session_id]


async def get_chat_orchestrator() -> ChatOrchestratorAgent:
    """Get or create the Chat Orchestrator agent instance."""
    registry = get_registry()
    agent = registry.get("chat_orchestrator")

    if not agent:
        logger.info("Creating new ChatOrchestratorAgent instance")
        agent = create_chat_orchestrator_agent()
        registry.register_agent("chat_orchestrator", agent)

    return agent


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/", response_model=None)
async def chat(
    request: ChatRequest,
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Main chat endpoint for interacting with AgentTwister.

    This endpoint:
    1. Accepts a user message
    2. Classifies the intent with high accuracy (≥90% target)
    3. Generates clarifying questions if needed
    4. Routes to appropriate specialist agents
    5. Returns the response

    Example:
        POST /api/v1/chat/
        {
            "message": "Analyze my chatbot for prompt injection",
            "stream": false
        }

    Response:
        {
            "success": true,
            "session_id": "...",
            "response_type": "agent_response",
            "intent": {...},
            "target_agent": "analyst",
            "agent_result": {...}
        }
    """
    start_time = datetime.utcnow()
    session_id = request.session_id or str(uuid.uuid4())

    try:
        # Get or create session
        session = get_session(session_id)

        # Create agent context
        context = AgentContext(
            session_id=session_id,
            messages=[m.dict() for m in session.messages],
            shared_data=request.context,
        )

        # Process the chat message
        result = await orchestrator.handle_chat_message(
            context=context,
            message=request.message,
            stream=request.stream,
        )

        # Update session with new messages
        session.messages.append({
            "type": "user",
            "content": request.message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if result.get("type") == "clarification":
            session.messages.append({
                "type": "assistant",
                "content": json.dumps(result.get("clarification", {})),
                "timestamp": datetime.utcnow().isoformat(),
            })
        elif result.get("type") == "answer":
            session.messages.append({
                "type": "assistant",
                "content": result.get("content", ""),
                "timestamp": datetime.utcnow().isoformat(),
            })

        session.updated_at = datetime.utcnow()

        # Build response
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        response_data = {
            "success": True,
            "session_id": session_id,
            "response_type": result.get("type", "unknown"),
            "processing_time_seconds": processing_time,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Add intent classification if present
        if "classification" in result:
            response_data["intent"] = result["classification"]

        # Add clarification if needed
        if result.get("clarification_needed") or result.get("type") == "clarification":
            response_data["clarification"] = result.get("clarification", {
                "questions": result.get("questions", []),
                "context": result.get("context", ""),
            })

        # Add agent routing info if applicable
        if result.get("target_agent"):
            response_data["target_agent"] = result["target_agent"]
            response_data["agent_result"] = result.get("agent_result")

        # Add direct response content
        if result.get("content"):
            response_data["message"] = result["content"]

        return response_data

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=str(e),
                error_type=type(e).__name__,
            ).dict(),
        )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Streaming chat endpoint for real-time progress updates.

    This endpoint returns Server-Sent Events (SSE) for real-time
    progress updates during request processing.

    Example:
        POST /api/v1/chat/stream
        {
            "message": "Analyze my chatbot for prompt injection"
        }

    Events:
        - progress: Processing progress updates
        - message: Chat messages
        - result: Final result
        - error: Errors
        - done: Stream completion
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events."""
        try:
            # Get or create session
            session = get_session(session_id)

            # Create agent context
            context = AgentContext(
                session_id=session_id,
                messages=[m.dict() for m in session.messages],
                shared_data=request.context,
            )

            # Stream processing
            async for progress in orchestrator.process_with_streaming(
                context=context,
                message=request.message,
            ):
                event = ChatStreamEvent(
                    event_type="progress",
                    session_id=session_id,
                    data={
                        "stage": progress.stage,
                        "message": progress.message,
                        "progress_percent": progress.progress_percent,
                        **progress.metadata,
                    },
                )
                yield f"event: progress\ndata: {event.json()}\n\n"

            # Get final result
            result = await orchestrator.handle_chat_message(
                context=context,
                message=request.message,
                stream=False,
            )

            # Send final result
            result_event = ChatStreamEvent(
                event_type="result",
                session_id=session_id,
                data=result,
            )
            yield f"event: result\ndata: {result_event.json()}\n\n"

            # Send done event
            done_event = ChatStreamEvent(
                event_type="done",
                session_id=session_id,
                data={"session_id": session_id},
            )
            yield f"event: done\ndata: {done_event.json()}\n\n"

        except Exception as e:
            logger.error(f"Chat stream error: {e}", exc_info=True)
            error_event = ChatStreamEvent(
                event_type="error",
                session_id=session_id,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            yield f"event: error\ndata: {error_event.json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/classify", response_model=None)
async def classify_intent(
    request: ChatRequest,
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Classify the intent of a user message.

    This endpoint performs only intent classification without
    executing any actions. Useful for understanding what
    AgentTwister would do with a request.

    Example:
        POST /api/v1/chat/classify
        {
            "message": "I want to test my chatbot for vulnerabilities"
        }

    Response:
        {
            "success": true,
            "classification": {
                "intent": "security_analysis",
                "confidence": 0.95,
                "confidence_level": "high",
                "target_agent": "analyst",
                ...
            }
        }
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        session = get_session(session_id)

        context = AgentContext(
            session_id=session_id,
            messages=[m.dict() for m in session.messages],
        )

        classification = await orchestrator.classify_intent(
            context=context,
            message=request.message,
        )

        return {
            "success": True,
            "classification": classification.to_dict(),
        }

    except Exception as e:
        logger.error(f"Intent classification error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=str(e),
                error_type=type(e).__name__,
            ).dict(),
        )


@router.get("/session/{session_id}", response_model=None)
async def get_session(
    session_id: str,
    include_summary: bool = Query(False, description="Include AI-generated summary"),
):
    """
    Get information about a chat session.

    Returns the conversation history and optional summary.

    Example:
        GET /api/v1/chat/session/abc-123?include_summary=true
    """
    session = _session_storage.get(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"Session '{session_id}' not found",
                error_type="SessionNotFound",
            ).dict(),
        )

    response_data = {
        "success": True,
        "session_id": session_id,
        "message_count": len(session.messages),
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "current_intent": session.current_intent.value if session.current_intent else None,
        "pending_actions": session.pending_actions,
    }

    if include_summary:
        response_data["summary"] = session.summary

    # Include recent messages (last 20)
    response_data["recent_messages"] = [
        m.dict() for m in session.messages[-20:]
    ]

    return response_data


@router.delete("/session/{session_id}", response_model=None)
async def delete_session(session_id: str):
    """
    Delete a chat session.

    Example:
        DELETE /api/v1/chat/session/abc-123
    """
    if session_id not in _session_storage:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"Session '{session_id}' not found",
                error_type="SessionNotFound",
            ).dict(),
        )

    del _session_storage[session_id]

    return {
        "success": True,
        "message": f"Session '{session_id}' deleted",
    }


@router.get("/capabilities", response_model=None)
async def get_capabilities(
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Get the capabilities of the Chat Orchestrator.

    Returns information about supported intents, agents, and features.

    Example:
        GET /api/v1/chat/capabilities
    """
    return {
        "success": True,
        "intents": [intent.value for intent in UserIntent],
        "agents": ["analyst", "planner", "payload_engineer", "formatter"],
        "features": [
            "intent_classification",
            "clarification_generation",
            "agent_routing",
            "streaming_responses",
            "conversation_memory",
            "multi_turn_conversations",
        ],
        "model": orchestrator.config.model_alias,
        "version": orchestrator.config.version,
    }


@router.get("/health", response_model=None)
async def health_check(
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Health check endpoint for the Chat Orchestrator.

    Example:
        GET /api/v1/chat/health
    """
    return {
        "success": True,
        "status": "healthy",
        "agent": orchestrator.config.name,
        "role": orchestrator.config.role.value,
        "model": orchestrator.config.model_alias,
        "state": orchestrator.state.value,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/clarify", response_model=None)
async def generate_clarification(
    request: ChatRequest,
    classification_data: Optional[Dict[str, Any]] = None,
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Generate clarifying questions for an ambiguous request.

    Example:
        POST /api/v1/chat/clarify
        {
            "message": "I want to test something",
            "classification_data": {...}
        }
    """
    try:
        session_id = request.session_id or str(uuid.uuid4())
        session = get_session(session_id)

        context = AgentContext(
            session_id=session_id,
            messages=[m.dict() for m in session.messages],
        )

        clarification = await orchestrator.generate_clarifying_questions(
            context=context,
            message=request.message,
            classification_result=classification_data,
        )

        return {
            "success": True,
            "clarification": clarification,
        }

    except Exception as e:
        logger.error(f"Clarification generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=str(e),
                error_type=type(e).__name__,
            ).dict(),
        )


@router.get("/sessions", response_model=None)
async def list_sessions(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
):
    """
    List all active chat sessions.

    Example:
        GET /api/v1/chat/sessions?limit=20
    """
    sessions = list(_session_storage.values())
    total = len(sessions)

    # Apply pagination
    paginated = sessions[offset:offset + limit]

    return {
        "success": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < total,
        "sessions": [
            {
                "session_id": s.session_id,
                "message_count": len(s.messages),
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "current_intent": s.current_intent.value if s.current_intent else None,
            }
            for s in paginated
        ],
    }


@router.post("/session/{session_id}/summary", response_model=None)
async def generate_session_summary(
    session_id: str,
    orchestrator: ChatOrchestratorAgent = Depends(get_chat_orchestrator),
):
    """
    Generate an AI summary of a conversation session.

    Example:
        POST /api/v1/chat/session/abc-123/summary
    """
    session = _session_storage.get(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(
                error=f"Session '{session_id}' not found",
                error_type="SessionNotFound",
            ).dict(),
        )

    try:
        context = AgentContext(
            session_id=session_id,
            messages=[m.dict() for m in session.messages],
        )

        summary_data = await orchestrator._get_conversation_summary(context)

        # Update session with summary
        session.summary = summary_data.get("summary")

        return {
            "success": True,
            "summary": summary_data,
        }

    except Exception as e:
        logger.error(f"Summary generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=str(e),
                error_type=type(e).__name__,
            ).dict(),
        )
