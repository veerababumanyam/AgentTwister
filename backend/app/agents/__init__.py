"""
AgentTwister Agent Framework

A Google ADK-inspired agent framework for building multi-agent red-teaming pipelines.
Provides base agent class, shared tools library, A2A protocol adapter, and
resilience patterns (exponential backoff, circuit breaker).
"""

from .base_agent import BaseAgent, AgentConfig, AgentContext
from .tools import (
    DatabaseReaderTool,
    DatabaseWriterTool,
    FileParserTool,
    HTTPCallerTool,
)
from .resilience import (
    ExponentialBackoff,
    CircuitBreaker,
    CircuitBreakerOpenError,
)
from .a2a import (
    A2AMessage,
    A2AProtocolAdapter,
    A2AStatusCode,
)
from .registry import AgentRegistry, get_registry
from .job_analyst import JobAnalystAgent, create_job_analyst_agent
from .planner import PlannerAgent, create_planner_agent
from .chat_orchestrator import (
    ChatOrchestratorAgent,
    create_chat_orchestrator_agent,
    IntentClassificationResult,
    IntentConfidence,
    StreamingProgress,
    UserIntent,
)
from .payload_engineer import (
    PayloadEngineerAgent,
    create_payload_engineer_agent,
    OutputFormat,
    EncodingStrategy,
    PayloadTemplatingEngine,
    EncodingHandler,
    PayloadGenerationRequest,
    PayloadGenerationResponse,
)
from .document_formatter import (
    DocumentFormatterAgent,
    create_document_formatter_agent,
)
from .architect import (
    ArchitectAgent,
    create_architect_agent,
    PayloadArchitecture,
    DetailedAttackDesign,
)
from .reviewer import (
    ReviewerAgent,
    create_reviewer_agent,
    PayloadReview,
    BatchReviewResult,
    ReviewStatus,
    SeverityLevel,
    StealthAssessment,
    ComplianceCheck,
    ReviewIssue,
)
from .formatter import (
    FormatterAgent,
    create_formatter_agent,
    FormattedReport,
    FormattedDocument,
    PayloadManifest,
    PayloadManifestItem,
    OutputFormat as FormatterOutputFormat,
    ReportType,
)

__all__ = [
    # Base Agent
    "BaseAgent",
    "AgentConfig",
    "AgentContext",
    # Tools
    "DatabaseReaderTool",
    "DatabaseWriterTool",
    "FileParserTool",
    "HTTPCallerTool",
    # Resilience
    "ExponentialBackoff",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    # A2A Protocol
    "A2AMessage",
    "A2AProtocolAdapter",
    "A2AStatusCode",
    # Registry
    "AgentRegistry",
    "get_registry",
    # Agents
    "JobAnalystAgent",
    "create_job_analyst_agent",
    "PlannerAgent",
    "create_planner_agent",
    "ChatOrchestratorAgent",
    "create_chat_orchestrator_agent",
    # Chat Orchestrator Types
    "IntentClassificationResult",
    "IntentConfidence",
    "StreamingProgress",
    "UserIntent",
    # Payload Engineer
    "PayloadEngineerAgent",
    "create_payload_engineer_agent",
    "OutputFormat",
    "EncodingStrategy",
    "PayloadTemplatingEngine",
    "EncodingHandler",
    "PayloadGenerationRequest",
    "PayloadGenerationResponse",
    # Document Formatter
    "DocumentFormatterAgent",
    "create_document_formatter_agent",
    # Architect Agent
    "ArchitectAgent",
    "create_architect_agent",
    "PayloadArchitecture",
    "DetailedAttackDesign",
    # Reviewer Agent
    "ReviewerAgent",
    "create_reviewer_agent",
    "PayloadReview",
    "BatchReviewResult",
    "ReviewStatus",
    "SeverityLevel",
    "StealthAssessment",
    "ComplianceCheck",
    "ReviewIssue",
    # Formatter Agent (Report Generation)
    "FormatterAgent",
    "create_formatter_agent",
    "FormattedReport",
    "FormattedDocument",
    "PayloadManifest",
    "PayloadManifestItem",
    "FormatterOutputFormat",
    "ReportType",
]
