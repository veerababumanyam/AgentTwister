"""
Chat Orchestrator Agent

The primary entry point for all user interactions in AgentTwister.
This agent is responsible for:
- Intent classification with ≥90% accuracy
- Clarifying question generation when intent is ambiguous
- Agent routing to appropriate specialist agents
- Progress streaming for real-time user feedback
- A2A protocol communication with all other agents

The Chat Orchestrator acts as the "front desk" of AgentTwister,
understanding user requests and directing them to the right specialist
while maintaining conversation context and providing clear feedback.
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
    Dict,
    List,
    Optional,
)

from .base_agent import (
    AgentConfig,
    AgentContext,
    AgentResponse,
    AgentRole,
    AgentState,
    BaseAgent,
    ToolDefinition,
)
from .a2a import (
    A2AConfig,
    A2AProtocolAdapter,
    A2ATaskInput,
    A2ATaskOutput,
    A2AMessage,
    A2AStatusCode,
)

logger = logging.getLogger(__name__)


# ============================================================
# INTENT CLASSIFICATION
# ============================================================

class UserIntent(str, Enum):
    """
    User intent categories for the Chat Orchestrator.

    These categories represent the primary actions users want to take.
    The orchestrator classifies incoming messages into these intents
    and routes to appropriate specialist agents.
    """

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
    HIGH = "high"  # ≥90% confidence
    MEDIUM = "medium"  # 70-89% confidence
    LOW = "low"  # <70% confidence


@dataclass
class IntentClassificationResult:
    """Result of intent classification."""
    intent: UserIntent
    confidence: float  # 0.0 to 1.0
    confidence_level: IntentConfidence
    entities: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    suggested_questions: List[str] = field(default_factory=list)
    target_agent: Optional[str] = None


@dataclass
class StreamingProgress:
    """Progress update for streaming responses."""
    stage: str  # e.g., "classifying", "routing", "executing"
    message: str
    progress_percent: float  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# CHAT ORCHESTRATOR AGENT
# ============================================================

class ChatOrchestratorAgent(BaseAgent):
    """
    Chat Orchestrator Agent - Primary entry point for user interactions.

    This agent serves as the central hub for all user interactions in AgentTwister:
    - Classifies user intent with high accuracy (≥90% target)
    - Generates clarifying questions when intent is ambiguous
    - Routes requests to appropriate specialist agents via A2A protocol
    - Streams progress updates for real-time user feedback
    - Maintains conversation context across multi-turn interactions

    Responsibilities:
    1. **Intent Classification**: Parse user messages and classify intent
    2. **Clarification**: Ask questions when intent is unclear
    3. **Routing**: Direct requests to the right specialist agent
    4. **Progress Streaming**: Provide real-time feedback during execution
    5. **Context Management**: Maintain conversation state and history

    Integration:
    - Uses LiteLLM with model alias "chat-orchestrator"
    - Communicates via A2A Protocol with all specialist agents
    - Stores conversation context in memory
    - Provides streaming responses for better UX
    """

    # ============================================================
    # SYSTEM PROMPTS
    # ============================================================

    INTENT_CLASSIFICATION_PROMPT = """You are the Intent Classifier for AgentTwister, an AI security research platform.

Your task is to classify user messages into intent categories with high accuracy.

**Available Intent Categories:**

1. **security_analysis** - User wants to analyze a system, application, or AI model for security vulnerabilities
   - Keywords: analyze, scan, check, find vulnerabilities, security assessment, audit

2. **vulnerability_scan** - User wants to scan for specific vulnerabilities or CVEs
   - Keywords: scan, vulnerability, CVE, exploit, security hole

3. **threat_modeling** - User wants to create or analyze threat models
   - Keywords: threat model, attack surface, threat landscape, risk assessment

4. **payload_generation** - User wants to generate security testing payloads
   - Keywords: generate payload, create payload, build attack, craft prompt

5. **payload_customization** - User wants to modify or customize existing payloads
   - Keywords: customize, modify, adapt payload, change parameters

6. **attack_simulation** - User wants to simulate an attack scenario
   - Keywords: simulate, test attack, red team, penetration test

7. **campaign_planning** - User wants to plan a security testing campaign
   - Keywords: plan, campaign, strategy, roadmap, approach

8. **test_strategy** - User wants to define testing methodology or approach
   - Keywords: strategy, methodology, approach, framework

9. **scope_definition** - User wants to define what's in/out of scope for testing
   - Keywords: scope, boundaries, what to test, exclude, include

10. **document_upload** - User wants to upload a document for analysis
    - Keywords: upload, attach, file, document, import

11. **document_analysis** - User wants to analyze an uploaded document
    - Keywords: analyze document, review file, parse document

12. **report_generation** - User wants to generate a report from findings
    - Keywords: report, generate document, export findings, summary

13. **system_help** - User is asking for help using AgentTwister
    - Keywords: help, how to, tutorial, guide, instructions

14. **general_question** - User is asking a general security question
    - Keywords: what is, explain, tell me about, definition

15. **status_check** - User wants to check the status of something
    - Keywords: status, where are we, progress, current state

**Classification Rules:**

1. Use the PRIMARY intent when multiple could apply
2. If intent is unclear (confidence < 70%), use "clarification_needed"
3. Extract relevant entities (target systems, frameworks, etc.)
4. Provide brief reasoning for the classification

**Response Format (JSON):**
```json
{
    "intent": "category_name",
    "confidence": 0.95,
    "entities": {
        "target_system": "...",
        "framework": "...",
        "attack_category": "..."
    },
    "reasoning": "Brief explanation",
    "target_agent": "agent_name",
    "clarification_needed": false,
    "suggested_questions": []
}
```

**Agent Routing:**
- security_analysis, vulnerability_scan, threat_modeling → "analyst"
- payload_generation, payload_customization, attack_simulation → "payload_engineer"
- campaign_planning, test_strategy, scope_definition → "planner"
- document_upload, document_analysis → "analyst"
- report_generation → "formatter"
- system_help, general_question, status_check → "orchestrator" (handle directly)"""

    CLARIFICATION_GENERATION_PROMPT = """You are the Clarification Generator for AgentTwister.

The user's message has unclear intent. Generate 2-4 specific, relevant questions
to understand what they want to accomplish.

**Guidelines:**
- Ask specific, actionable questions
- Avoid yes/no questions when possible
- Provide context about what information you need
- Keep questions concise and clear

**Response Format (JSON):**
```json
{
    "questions": [
        "What specific system or application are you looking to test?",
        "Are you looking for a specific type of vulnerability (e.g., prompt injection, data leakage)?"
    ],
    "context": "I need to understand your testing goals to route your request effectively."
}
```"""

    CONVERSATION_SUMMARY_PROMPT = """You are the Conversation Summarizer for AgentTwister.

Summarize the recent conversation into key points that maintain context for future interactions.

**Response Format (JSON):**
```json
{
    "summary": "Brief summary of the conversation",
    "key_points": ["point 1", "point 2", "point 3"],
    "current_intent": "intent_name",
    "pending_actions": ["action 1", "action 2"]
}
```"""

    # ============================================================
    # INITIALIZATION
    # ============================================================

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the Chat Orchestrator Agent.

        Args:
            config: Optional agent configuration. Uses defaults if not provided.
        """
        if config is None:
            config = AgentConfig(
                name="chat_orchestrator",
                role=AgentRole.CHAT_ORCHESTRATOR,
                model_alias="chat-orchestrator",
                temperature=0.3,  # Lower temperature for consistent classification
                max_tokens=4096,
                enable_long_term_memory=True,
                memory_collection="chat_orchestrator_memories",
                enable_streaming=True,
            )
        super().__init__(config)

        # Initialize A2A protocol adapter for inter-agent communication
        self._a2a = A2AProtocolAdapter(
            config=A2AConfig(
                agent_name="chat_orchestrator",
                agent_role="chat_orchestrator",
                agent_version="1.0.0",
            ),
        )

        # Register A2A message handlers
        self._register_a2a_handlers()

        # Intent to agent mapping
        self._intent_to_agent = {
            UserIntent.SECURITY_ANALYSIS: "analyst",
            UserIntent.VULNERABILITY_SCAN: "analyst",
            UserIntent.THREAT_MODELING: "analyst",
            UserIntent.PAYLOAD_GENERATION: "payload_engineer",
            UserIntent.PAYLOAD_CUSTOMIZATION: "payload_engineer",
            UserIntent.ATTACK_SIMULATION: "payload_engineer",
            UserIntent.CAMPAIGN_PLANNING: "planner",
            UserIntent.TEST_STRATEGY: "planner",
            UserIntent.SCOPE_DEFINITION: "planner",
            UserIntent.DOCUMENT_UPLOAD: "analyst",
            UserIntent.DOCUMENT_ANALYSIS: "analyst",
            UserIntent.REPORT_GENERATION: "formatter",
            UserIntent.SYSTEM_HELP: None,  # Handle directly
            UserIntent.GENERAL_QUESTION: None,  # Handle directly
            UserIntent.STATUS_CHECK: None,  # Handle directly
        }

        logger.info("ChatOrchestratorAgent initialized with A2A protocol support")

    def _register_a2a_handlers(self) -> None:
        """Register A2A protocol message handlers."""
        self._a2a_handlers = {
            "classify_intent": self._handle_classify_intent,
            "route_to_agent": self._handle_route_to_agent,
            "health_check": self._handle_health_check,
            "conversation_context": self._handle_conversation_context,
        }

    # ============================================================
    # MAIN PROCESS METHOD
    # ============================================================

    async def process(
        self,
        context: AgentContext,
        input_data: Dict[str, Any],
    ) -> AgentResponse:
        """
        Process the agent's main task.

        This is the primary entry point for agent execution.
        Routes to appropriate handler based on input data.

        Args:
            context: Agent context with session ID, shared data, conversation history
            input_data: Structured input data containing task type and parameters

        Returns:
            Agent response with structured results
        """
        start_time = datetime.utcnow()
        task_type = input_data.get("task_type", "chat")

        try:
            # Update conversation history
            user_message = input_data.get("message", "")
            if user_message:
                context.messages.append({
                    "role": "user",
                    "content": user_message,
                })

            # Route to appropriate handler
            if task_type == "chat":
                result = await self.handle_chat_message(
                    context=context,
                    message=user_message,
                    stream=input_data.get("stream", False),
                )
                response_content = json.dumps(result, default=str)

            elif task_type == "classify_intent":
                result = await self.classify_intent(
                    context=context,
                    message=user_message,
                )
                response_content = json.dumps(result.to_dict(), default=str)

            elif task_type == "clarify":
                result = await self.generate_clarifying_questions(
                    context=context,
                    message=user_message,
                    classification_result=input_data.get("classification_result"),
                )
                response_content = json.dumps(result, default=str)

            elif task_type == "route":
                result = await self.route_to_agent(
                    context=context,
                    intent=input_data.get("intent"),
                    agent_name=input_data.get("agent_name"),
                    input_data=input_data.get("input_data", {}),
                )
                response_content = json.dumps(result, default=str)

            else:
                # Unknown task type - provide help
                result = self._get_help_response()
                response_content = json.dumps(result, default=str)

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Update conversation history with assistant response
            context.messages.append({
                "role": "assistant",
                "content": response_content,
            })

            return AgentResponse(
                agent_name=self.config.name,
                agent_role=self.config.role,
                content=response_content,
                state=AgentState.COMPLETED,
                metadata={
                    "task_type": task_type,
                    "processing_time_seconds": processing_time,
                },
            )

        except Exception as e:
            logger.error(f"ChatOrchestratorAgent processing failed: {e}", exc_info=True)
            return AgentResponse(
                agent_name=self.config.name,
                agent_role=self.config.role,
                content="",
                state=AgentState.FAILED,
                error=str(e),
            )

    # ============================================================
    # INTENT CLASSIFICATION
    # ============================================================

    async def classify_intent(
        self,
        context: AgentContext,
        message: str,
    ) -> IntentClassificationResult:
        """
        Classify user intent from their message.

        Uses LLM with structured prompt for ≥90% accuracy classification.
        Extracts entities and determines target agent.

        Args:
            context: Agent context
            message: User's message

        Returns:
            IntentClassificationResult with classified intent and metadata
        """
        if not message or not message.strip():
            return IntentClassificationResult(
                intent=UserIntent.CLARIFICATION_NEEDED,
                confidence=0.0,
                confidence_level=IntentConfidence.LOW,
                reasoning="Empty message",
                suggested_questions=[
                    "How can I help you with your security research today?",
                    "Are you looking to analyze systems, generate payloads, or plan a campaign?",
                ],
            )

        # Build classification prompt with few-shot examples
        classification_prompt = f"""{self.INTENT_CLASSIFICATION_PROMPT}

**Examples:**

User: "I want to test my chatbot for prompt injection vulnerabilities"
Intent: payload_generation
Confidence: 0.95
Target Agent: payload_engineer

User: "Can you help me analyze this API documentation for security issues?"
Intent: document_analysis
Confidence: 0.92
Target Agent: analyst

User: "I need to plan a comprehensive red team engagement for my AI application"
Intent: campaign_planning
Confidence: 0.90
Target Agent: planner

User: "How do I use AgentTwister?"
Intent: system_help
Confidence: 0.98
Target Agent: orchestrator

**Now classify this user message:**
{message}

Respond ONLY with valid JSON following the format above."""

        try:
            # Get LLM classification
            llm_response = await self.llm_generate(
                classification_prompt,
                context,
                temperature=0.2,  # Low temperature for consistent classification
                max_tokens=1000,
            )

            # Parse LLM response
            classification_data = self._clean_and_parse_json(llm_response)

            # Extract intent
            intent_str = classification_data.get("intent", "general_question")
            try:
                intent = UserIntent(intent_str)
            except ValueError:
                # If intent is not recognized, default to clarification
                intent = UserIntent.CLARIFICATION_NEEDED

            confidence = float(classification_data.get("confidence", 0.7))
            confidence_level = self._get_confidence_level(confidence)

            # Determine target agent
            target_agent = classification_data.get("target_agent")
            if not target_agent:
                target_agent = self._intent_to_agent.get(intent)

            # Create result
            result = IntentClassificationResult(
                intent=intent,
                confidence=confidence,
                confidence_level=confidence_level,
                entities=classification_data.get("entities", {}),
                reasoning=classification_data.get("reasoning", ""),
                suggested_questions=classification_data.get("suggested_questions", []),
                target_agent=target_agent,
            )

            # Store classification in memory
            await self.save_to_memory(
                f"last_intent_{context.session_id}",
                result.to_dict(),
                context,
            )

            logger.info(
                f"Classified intent: {intent.value} "
                f"(confidence: {confidence:.2f}, target: {target_agent})"
            )
            return result

        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            # Return clarification needed on error
            return IntentClassificationResult(
                intent=UserIntent.CLARIFICATION_NEEDED,
                confidence=0.0,
                confidence_level=IntentConfidence.LOW,
                reasoning=f"Classification error: {str(e)}",
                suggested_questions=[
                    "Could you please rephrase your request?",
                    "What would you like to accomplish with AgentTwister?",
                ],
            )

    def _get_confidence_level(self, confidence: float) -> IntentConfidence:
        """Convert confidence score to confidence level."""
        if confidence >= 0.90:
            return IntentConfidence.HIGH
        elif confidence >= 0.70:
            return IntentConfidence.MEDIUM
        else:
            return IntentConfidence.LOW

    # ============================================================
    # CLARIFYING QUESTIONS
    # ============================================================

    async def generate_clarifying_questions(
        self,
        context: AgentContext,
        message: str,
        classification_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate clarifying questions when intent is ambiguous.

        Args:
            context: Agent context
            message: User's message
            classification_result: Optional prior classification result

        Returns:
            Dict with questions and context
        """
        try:
            # Build clarification prompt
            clarification_prompt = f"""{self.CLARIFICATION_GENERATION_PROMPT}

**User's message:**
{message}

**Classification context:**
{json.dumps(classification_result, indent=2) if classification_result else "None"}

Generate 2-4 specific clarifying questions."""

            # Get LLM response
            llm_response = await self.llm_generate(
                clarification_prompt,
                context,
                temperature=0.5,
                max_tokens=800,
            )

            # Parse response
            result = self._clean_and_parse_json(llm_response)

            return {
                "clarification_needed": True,
                "questions": result.get("questions", [
                    "Could you provide more details about what you'd like to accomplish?",
                    "What specific system or feature are you working with?",
                ]),
                "context": result.get("context", "I need more information to help you effectively."),
            }

        except Exception as e:
            logger.error(f"Clarification generation failed: {e}", exc_info=True)
            return {
                "clarification_needed": True,
                "questions": [
                    "Could you please provide more details about your request?",
                    "What are you trying to accomplish with AgentTwister?",
                ],
                "context": "I need to understand your goals better.",
            }

    # ============================================================
    # CHAT MESSAGE HANDLING
    # ============================================================

    async def handle_chat_message(
        self,
        context: AgentContext,
        message: str,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Handle a chat message from the user.

        This is the main entry point for chat interactions.
        Classifies intent, generates clarifications if needed, and routes to agents.

        Args:
            context: Agent context
            message: User's message
            stream: Whether to stream progress updates

        Returns:
            Dict with response data
        """
        # Step 1: Classify intent
        classification = await self.classify_intent(context, message)

        # Step 2: Check if clarification is needed
        if (
            classification.intent == UserIntent.CLARIFICATION_NEEDED or
            classification.confidence_level == IntentConfidence.LOW
        ):
            clarification = await self.generate_clarifying_questions(
                context, message, classification.to_dict()
            )
            return {
                "type": "clarification",
                "classification": classification.to_dict(),
                **clarification,
            }

        # Step 3: Handle intents that don't require routing
        if classification.intent in [
            UserIntent.SYSTEM_HELP,
            UserIntent.GENERAL_QUESTION,
        ]:
            return await self._handle_general_inquiry(context, classification)

        if classification.intent == UserIntent.STATUS_CHECK:
            return await self._handle_status_check(context, classification)

        # Step 4: Route to specialist agent
        if classification.target_agent:
            agent_result = await self.route_to_agent(
                context=context,
                intent=classification.intent,
                agent_name=classification.target_agent,
                input_data={
                    "message": message,
                    "entities": classification.entities,
                    "classification": classification.to_dict(),
                },
            )
            return {
                "type": "agent_response",
                "classification": classification.to_dict(),
                "target_agent": classification.target_agent,
                "agent_result": agent_result,
            }

        # Fallback response
        return {
            "type": "clarification",
            "classification": classification.to_dict(),
            "clarification_needed": True,
            "questions": [
                "I'm not sure how to help with that request. Could you provide more details?",
            ],
            "context": "Please rephrase your request.",
        }

    # ============================================================
    # AGENT ROUTING
    # ============================================================

    async def route_to_agent(
        self,
        context: AgentContext,
        intent: UserIntent,
        agent_name: str,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Route request to a specialist agent via A2A protocol.

        Args:
            context: Agent context
            intent: Classified user intent
            agent_name: Target agent name
            input_data: Data to send to target agent

        Returns:
            Dict with agent response
        """
        try:
            # Determine task type for target agent
            task_type = self._intent_to_task_type(intent)

            # Prepare A2A message
            a2a_task_data = {
                **input_data,
                "task_type": task_type,
                "conversation_id": context.session_id,
            }

            # Send via A2A protocol
            response = await self._a2a.send_task(
                target_agent=agent_name,
                task_type=task_type,
                data=a2a_task_data,
                conversation_id=context.session_id,
                timeout=self.config.timeout_seconds,
            )

            # Check if response was successful
            if response.status.code == A2AStatusCode.OK:
                return {
                    "success": True,
                    "agent": agent_name,
                    "task_type": task_type,
                    "result": response.result.data if response.result else {},
                }
            else:
                return {
                    "success": False,
                    "agent": agent_name,
                    "error": response.status.message,
                    "status_code": response.status.code.value,
                }

        except ValueError as e:
            # Agent not found
            logger.error(f"Agent '{agent_name}' not found: {e}")
            return {
                "success": False,
                "agent": agent_name,
                "error": f"Agent '{agent_name}' is not available",
            }
        except Exception as e:
            logger.error(f"Agent routing failed: {e}", exc_info=True)
            return {
                "success": False,
                "agent": agent_name,
                "error": str(e),
            }

    def _intent_to_task_type(self, intent: UserIntent) -> str:
        """Convert intent to task type for A2A communication."""
        task_mapping = {
            UserIntent.SECURITY_ANALYSIS: "analyze",
            UserIntent.VULNERABILITY_SCAN: "scan",
            UserIntent.THREAT_MODELING: "threat_model",
            UserIntent.PAYLOAD_GENERATION: "generate",
            UserIntent.PAYLOAD_CUSTOMIZATION: "customize",
            UserIntent.ATTACK_SIMULATION: "simulate",
            UserIntent.CAMPAIGN_PLANNING: "plan_campaign",
            UserIntent.TEST_STRATEGY: "create_strategy",
            UserIntent.SCOPE_DEFINITION: "define_scope",
            UserIntent.DOCUMENT_UPLOAD: "process_document",
            UserIntent.DOCUMENT_ANALYSIS: "analyze_document",
            UserIntent.REPORT_GENERATION: "generate_report",
        }
        return task_mapping.get(intent, "process")

    # ============================================================
    # STREAMING PROGRESS
    # ============================================================

    async def process_with_streaming(
        self,
        context: AgentContext,
        message: str,
    ) -> AsyncIterator[StreamingProgress]:
        """
        Process user message with streaming progress updates.

        Args:
            context: Agent context
            message: User's message

        Yields:
            StreamingProgress updates
        """
        # Stage 1: Classifying intent
        yield StreamingProgress(
            stage="classifying",
            message="Understanding your request...",
            progress_percent=0.1,
        )

        classification = await self.classify_intent(context, message)

        yield StreamingProgress(
            stage="classified",
            message=f"Identified intent: {classification.intent.value}",
            progress_percent=0.3,
            metadata={"intent": classification.intent.value},
        )

        # Stage 2: Checking for clarification
        if classification.confidence_level == IntentConfidence.LOW:
            yield StreamingProgress(
                stage="clarifying",
                message="I need a bit more information...",
                progress_percent=0.5,
            )

            clarification = await self.generate_clarifying_questions(
                context, message, classification.to_dict()
            )

            yield StreamingProgress(
                stage="clarification_ready",
                message="Here are some questions to help me understand better:",
                progress_percent=1.0,
                metadata={
                    "questions": clarification.get("questions", []),
                },
            )
            return

        # Stage 3: Routing to agent
        if classification.target_agent:
            yield StreamingProgress(
                stage="routing",
                message=f"Routing to {classification.target_agent} agent...",
                progress_percent=0.5,
                metadata={"target_agent": classification.target_agent},
            )

            yield StreamingProgress(
                stage="executing",
                message=f"{classification.target_agent.capitalize()} is working on your request...",
                progress_percent=0.7,
            )

            result = await self.route_to_agent(
                context=context,
                intent=classification.intent,
                agent_name=classification.target_agent,
                input_data={"message": message, "entities": classification.entities},
            )

            yield StreamingProgress(
                stage="completed",
                message="Done!",
                progress_percent=1.0,
                metadata={"result": result},
            )
        else:
            # Handle directly
            yield StreamingProgress(
                stage="responding",
                message="Processing your request...",
                progress_percent=0.7,
            )

            response = await self._handle_general_inquiry(context, classification)

            yield StreamingProgress(
                stage="completed",
                message="Done!",
                progress_percent=1.0,
                metadata={"response": response},
            )

    # ============================================================
    # HANDLERS FOR DIRECT INTENTS
    # ============================================================

    async def _handle_general_inquiry(
        self,
        context: AgentContext,
        classification: IntentClassificationResult,
    ) -> Dict[str, Any]:
        """Handle general questions and system help requests."""
        if classification.intent == UserIntent.SYSTEM_HELP:
            return {
                "type": "help",
                "content": self._get_help_text(),
            }

        if classification.intent == UserIntent.GENERAL_QUESTION:
            # Use LLM to answer the question
            answer = await self.llm_generate(
                f"""You are AgentTwister's helpful assistant. Answer this question about AI security:

{context.messages[-1].get('content', '') if context.messages else ''}

Provide a concise, helpful response. If the question is about security testing,
mention that AgentTwister can help with authorized testing only.""",
                context,
                temperature=0.7,
            )
            return {
                "type": "answer",
                "content": answer,
            }

        return {
            "type": "response",
            "content": "I'm here to help with your security research needs.",
        }

    async def _handle_status_check(
        self,
        context: AgentContext,
        classification: IntentClassificationResult,
    ) -> Dict[str, Any]:
        """Handle status check requests."""
        # Get conversation summary
        summary = await self._get_conversation_summary(context)

        return {
            "type": "status",
            "current_state": "active",
            "conversation_summary": summary,
            "available_agents": list(self._intent_to_agent.values()),
        }

    async def _get_conversation_summary(self, context: AgentContext) -> Dict[str, Any]:
        """Generate a summary of the current conversation."""
        if not context.messages:
            return {"summary": "New conversation", "key_points": []}

        try:
            summary_prompt = f"""{self.CONVERSATION_SUMMARY_PROMPT}

**Conversation:**
{json.dumps(context.messages[-10:], indent=2)}

Summarize this conversation."""

            response = await self.llm_generate(
                summary_prompt,
                context,
                temperature=0.3,
            )

            return self._clean_and_parse_json(response)

        except Exception as e:
            logger.error(f"Conversation summary failed: {e}")
            return {
                "summary": f"Conversation has {len(context.messages)} messages",
                "key_points": [],
            }

    # ============================================================
    # A2A PROTOCOL HANDLERS
    # ============================================================

    async def handle_a2a_request(self, message: A2AMessage) -> A2AMessage:
        """
        Handle incoming A2A protocol request.

        Args:
            message: A2A message

        Returns:
            A2A response message
        """
        if not message.task:
            return self._a2a.create_response(
                message,
                status_code=A2AStatusCode.BAD_REQUEST,
                status_message="No task data in message",
            )

        task_type = message.task.type
        handler = self._a2a_handlers.get(task_type)

        if not handler:
            return self._a2a.create_response(
                message,
                status_code=A2AStatusCode.NOT_FOUND,
                status_message=f"Unknown task type: {task_type}",
            )

        try:
            # Create context from A2A message
            context = AgentContext(
                session_id=message.header.conversation_id or "a2a_session",
            )

            # Execute handler
            result = await handler(message.task.data, context)

            # Return A2A response
            return self._a2a.create_response(
                message,
                output_data=result if isinstance(result, dict) else {"result": result},
                output_type=task_type + "_result",
            )

        except Exception as e:
            logger.error(f"A2A request handler failed: {e}", exc_info=True)
            return self._a2a.create_response(
                message,
                status_code=A2AStatusCode.INTERNAL_ERROR,
                status_message=str(e),
            )

    async def _handle_classify_intent(self, data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """A2A handler for intent classification."""
        result = await self.classify_intent(
            context=context,
            message=data.get("message", ""),
        )
        return result.to_dict()

    async def _handle_route_to_agent(self, data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """A2A handler for agent routing."""
        intent_str = data.get("intent")
        try:
            intent = UserIntent(intent_str)
        except ValueError:
            intent = UserIntent.SECURITY_ANALYSIS

        return await self.route_to_agent(
            context=context,
            intent=intent,
            agent_name=data.get("agent_name", "analyst"),
            input_data=data.get("input_data", {}),
        )

    async def _handle_health_check(self, data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """A2A health check handler."""
        return {
            "status": "healthy",
            "agent": self.config.name,
            "role": self.config.role.value,
            "model": self.config.model_alias,
            "timestamp": datetime.utcnow().isoformat(),
            "capabilities": {
                "intent_classification": True,
                "clarification_generation": True,
                "agent_routing": True,
                "streaming_responses": True,
                "supported_intents": [i.value for i in UserIntent],
            },
        }

    async def _handle_conversation_context(self, data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """A2A handler for conversation context requests."""
        return {
            "session_id": context.session_id,
            "message_count": len(context.messages),
            "shared_data": context.shared_data,
            "summary": await self._get_conversation_summary(context),
        }

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _clean_and_parse_json(self, response: str) -> Dict[str, Any]:
        """
        Clean and parse JSON from LLM response.

        LLMs sometimes add markdown formatting or other text around JSON.
        This extracts valid JSON.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed JSON dict
        """
        # Try direct parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        if "```json" in response:
            json_part = response.split("```json")[1].split("```")[0].strip()
            return json.loads(json_part)
        elif "```" in response:
            json_part = response.split("```")[1].split("```")[0].strip()
            return json.loads(json_part)

        # Try finding first { and last }
        first_brace = response.find("{")
        last_brace = response.rfind("}")
        if first_brace >= 0 and last_brace > first_brace:
            json_part = response[first_brace:last_brace + 1]
            return json.loads(json_part)

        raise ValueError("Could not extract valid JSON from LLM response")

    def _get_help_text(self) -> str:
        """Get help text for users."""
        return """# AgentTwister Help

Welcome to AgentTwister - an AI-powered security research platform for authorized red-teaming.

## What I Can Help With

1. **Security Analysis**
   - Analyze systems for vulnerabilities
   - Scan for specific security issues
   - Create threat models

2. **Payload Generation**
   - Generate security testing payloads
   - Customize existing payloads
   - Simulate attack scenarios

3. **Campaign Planning**
   - Plan comprehensive testing campaigns
   - Define testing strategies
   - Set testing scope

4. **Document Processing**
   - Upload and analyze documents
   - Generate reports from findings

## How to Use

Just type your request in natural language, and I'll:
1. Understand what you want to do
2. Ask clarifying questions if needed
3. Route your request to the right specialist
4. Provide real-time progress updates

## Example Queries

- "Analyze my chatbot for prompt injection vulnerabilities"
- "Generate a payload to test for data leakage"
- "Plan a red team engagement for my AI application"
- "Upload this security document for analysis"

**Important:** All testing must be authorized and scoped.
"""

    def _get_help_response(self) -> Dict[str, Any]:
        """Get full help response."""
        return {
            "type": "help",
            "content": self._get_help_text(),
            "supported_intents": [i.value for i in UserIntent],
            "available_agents": ["analyst", "planner", "payload_engineer", "formatter"],
        }


# ============================================================
# INTENT CLASSIFICATION RESULT EXTENSION
# ============================================================

def to_dict_method(self) -> Dict[str, Any]:
    """Convert IntentClassificationResult to dict."""
    return {
        "intent": self.intent.value if isinstance(self.intent, UserIntent) else self.intent,
        "confidence": self.confidence,
        "confidence_level": self.confidence_level.value,
        "entities": self.entities,
        "reasoning": self.reasoning,
        "suggested_questions": self.suggested_questions,
        "target_agent": self.target_agent,
    }


# Add to_dict method to IntentClassificationResult
IntentClassificationResult.to_dict = to_dict_method


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_chat_orchestrator_agent(
    name: str = "chat_orchestrator",
    model_alias: str = "chat-orchestrator",
    **config_kwargs,
) -> ChatOrchestratorAgent:
    """
    Factory function to create a configured ChatOrchestratorAgent.

    Args:
        name: Agent name
        model_alias: LiteLLM model alias
        **config_kwargs: Additional configuration

    Returns:
        Configured ChatOrchestratorAgent instance
    """
    from .tools import ToolFactory

    # Create agent configuration
    config = AgentConfig(
        name=name,
        role=AgentRole.CHAT_ORCHESTRATOR,
        model_alias=model_alias,
        temperature=0.3,
        enable_streaming=True,
        **config_kwargs,
    )

    # Create tools for the agent
    tools = [
        ToolFactory.get_file_parser().to_definition(),
        ToolFactory.get_database_reader().to_definition(),
        ToolFactory.get_database_writer().to_definition(),
    ]

    # Create agent instance
    agent = ChatOrchestratorAgent(config=config)
    for tool in tools:
        agent.register_tool(tool)

    logger.info(f"Created ChatOrchestratorAgent: {name} with model {model_alias}")
    return agent
