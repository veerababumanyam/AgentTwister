"""
Chat Data Models

Defines the schema for chat interactions with the Chat Orchestrator agent.
These models are used for the chat API endpoints and streaming responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class UserIntent(str, Enum):
    """User intent categories for chat interactions."""

    # Security Analysis Intents
    SECURITY_ANALYSIS = "security_analysis"
    VULNERABILITY_SCAN = "vulnerability_scan"
    THREAT_MODELING = "threat_modeling"

    # Payload Generation Intents
    PAYLOAD_GENERATION = "payload_generation"
    PAYLOAD_CUSTOMIZATION = "payload_customization"
    ATTACK_SIMULATION = "attack_simulation"

    # Planning and Strategy Intents
    CAMPAIGN_PLANNING = "campaign_planning"
    TEST_STRATEGY = "test_strategy"
    SCOPE_DEFINITION = "scope_definition"

    # Document and Data Intents
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_ANALYSIS = "document_analysis"
    REPORT_GENERATION = "report_generation"

    # System and Help Intents
    SYSTEM_HELP = "system_help"
    GENERAL_QUESTION = "general_question"
    STATUS_CHECK = "status_check"

    # Clarification Needed
    CLARIFICATION_NEEDED = "clarification_needed"


class IntentConfidence(str, Enum):
    """Confidence levels for intent classification."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MessageType(str, Enum):
    """Types of messages in the chat system."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    PROGRESS = "progress"


class ChatMessage(BaseModel):
    """A single message in the chat conversation."""

    id: str = Field(default_factory=lambda: f"msg_{datetime.utcnow().timestamp()}")
    type: MessageType
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Optional fields for specific message types
    intent: Optional[UserIntent] = None
    confidence: Optional[float] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)


class IntentClassification(BaseModel):
    """Intent classification result."""

    intent: UserIntent
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    confidence_level: IntentConfidence
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    reasoning: str = Field(default="", description="Explanation for the classification")
    target_agent: Optional[str] = Field(None, description="Target agent for routing")


class ClarificationResponse(BaseModel):
    """Response when clarification is needed."""

    clarification_needed: bool = True
    questions: List[str] = Field(
        ...,
        description="List of clarifying questions to ask the user",
        min_length=1,
    )
    context: str = Field(
        ...,
        description="Additional context about why clarification is needed",
    )


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., min_length=1, max_length=10000, description="User's message")
    session_id: Optional[str] = Field(
        None,
        description="Session ID for conversation continuity. Generated if not provided.",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream progress updates",
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context for the request",
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    success: bool
    session_id: str
    response_type: str = Field(
        ...,
        description="Type of response: 'answer', 'clarification', 'agent_response', etc.",
    )

    # Content
    message: Optional[str] = Field(None, description="Main response message")
    content: Optional[str] = Field(None, description="Response content (alternative to message)")

    # Intent classification
    intent: Optional[IntentClassification] = Field(None, description="Classified intent")

    # Clarification (when needed)
    clarification: Optional[ClarificationResponse] = Field(
        None,
        description="Clarification questions if intent is unclear",
    )

    # Agent routing (when applicable)
    target_agent: Optional[str] = Field(None, description="Agent that handled the request")
    agent_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Result from specialist agent",
    )

    # Metadata
    processing_time_seconds: float = Field(
        ...,
        description="Time taken to process the request",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatStreamEvent(BaseModel):
    """A single event in a streaming chat response."""

    event_type: str = Field(
        ...,
        description="Type of event: 'progress', 'message', 'result', 'error', 'done'",
    )
    session_id: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProgressUpdate(BaseModel):
    """Progress update for streaming responses."""

    stage: str = Field(..., description="Current stage of processing")
    message: str = Field(..., description="Human-readable progress message")
    progress_percent: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Progress from 0.0 to 1.0",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationHistory(BaseModel):
    """Conversation history for a session."""

    session_id: str
    messages: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: Optional[str] = Field(None, description="Conversation summary")
    current_intent: Optional[UserIntent] = Field(None, description="Current active intent")
    pending_actions: List[str] = Field(default_factory=list)


class ConversationSummary(BaseModel):
    """Summary of a conversation."""

    summary: str
    key_points: List[str] = Field(default_factory=list)
    current_intent: Optional[str] = None
    pending_actions: List[str] = Field(default_factory=list)


class AgentCapabilities(BaseModel):
    """Capabilities exposed by the Chat Orchestrator."""

    intents: List[UserIntent] = Field(
        ...,
        description="List of supported intents",
    )
    agents: List[str] = Field(
        ...,
        description="List of available specialist agents",
    )
    features: List[str] = Field(
        default_factory=lambda: [
            "intent_classification",
            "clarification_generation",
            "agent_routing",
            "streaming_responses",
            "conversation_memory",
        ],
        description="Supported features",
    )


class HealthStatus(BaseModel):
    """Health status of the Chat Orchestrator."""

    status: str = Field(..., description="Health status: 'healthy', 'degraded', 'unhealthy'")
    agent: str = Field(..., description="Agent name")
    role: str = Field(..., description="Agent role")
    model: str = Field(..., description="LLM model being used")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    capabilities: AgentCapabilities


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Type of error")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# ============================================================
# REQUEST/RESPONSE PAIRS FOR STREAMING
# ============================================================

class StreamChunk(BaseModel):
    """A chunk of streaming data."""

    chunk: str
    is_final: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamRequest(ChatRequest):
    """Request for streaming chat."""

    message: str
    session_id: Optional[str] = None


class StreamResponse(BaseModel):
    """Wrapper for streaming responses."""

    session_id: str
    events: List[ChatStreamEvent]
    is_complete: bool = False
