/**
 * Chat Interface Types
 *
 * TypeScript types for the chat interface that mirror the backend Pydantic models.
 * These types ensure type safety between the frontend and backend.
 */

// ============================================================================
// ENUMS
// ============================================================================

/**
 * User intent categories for chat interactions.
 * Mirrors backend: backend/app/models/chat.py::UserIntent
 */
export enum UserIntent {
  // Security Analysis Intents
  SECURITY_ANALYSIS = "security_analysis",
  VULNERABILITY_SCAN = "vulnerability_scan",
  THREAT_MODELING = "threat_modeling",

  // Payload Generation Intents
  PAYLOAD_GENERATION = "payload_generation",
  PAYLOAD_CUSTOMIZATION = "payload_customization",
  ATTACK_SIMULATION = "attack_simulation",

  // Planning and Strategy Intents
  CAMPAIGN_PLANNING = "campaign_planning",
  TEST_STRATEGY = "test_strategy",
  SCOPE_DEFINITION = "scope_definition",

  // Document and Data Intents
  DOCUMENT_UPLOAD = "document_upload",
  DOCUMENT_ANALYSIS = "document_analysis",
  REPORT_GENERATION = "report_generation",

  // System and Help Intents
  SYSTEM_HELP = "system_help",
  GENERAL_QUESTION = "general_question",
  STATUS_CHECK = "status_check",

  // Clarification Needed
  CLARIFICATION_NEEDED = "clarification_needed",
}

/**
 * Confidence levels for intent classification.
 * Mirrors backend: backend/app/models/chat.py::IntentConfidence
 */
export enum IntentConfidence {
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
}

/**
 * Types of messages in the chat system.
 * Mirrors backend: backend/app/models/chat.py::MessageType
 */
export enum MessageType {
  USER = "user",
  ASSISTANT = "assistant",
  SYSTEM = "system",
  PROGRESS = "progress",
}

/**
 * Streaming event types from the backend.
 * Mirrors backend: backend/app/models/chat.py::ChatStreamEvent
 */
export enum StreamEventType {
  PROGRESS = "progress",
  MESSAGE = "message",
  RESULT = "result",
  ERROR = "error",
  DONE = "done",
}

// ============================================================================
// INTERFACES
// ============================================================================

/**
 * A single message in the chat conversation.
 * Mirrors backend: backend/app/models/chat.py::ChatMessage
 */
export interface ChatMessage {
  id: string;
  type: MessageType;
  content: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  intent?: UserIntent;
  confidence?: number;
  tool_calls?: ToolCall[];
}

/**
 * A tool call made during message processing.
 */
export interface ToolCall {
  id: string;
  name: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
}

/**
 * Intent classification result.
 * Mirrors backend: backend/app/models/chat.py::IntentClassification
 */
export interface IntentClassification {
  intent: UserIntent;
  confidence: number;
  confidence_level: IntentConfidence;
  entities?: Record<string, unknown>;
  reasoning?: string;
  target_agent?: string;
}

/**
 * Clarification response when intent is unclear.
 * Mirrors backend: backend/app/models/chat.py::ClarificationResponse
 */
export interface ClarificationResponse {
  clarification_needed: boolean;
  questions: string[];
  context: string;
}

/**
 * Request payload for chat endpoint.
 * Mirrors backend: backend/app/models/chat.py::ChatRequest
 */
export interface ChatRequest {
  message: string;
  session_id?: string;
  stream?: boolean;
  context?: Record<string, unknown>;
  files?: FileUpload[];
}

/**
 * File upload metadata.
 */
export interface FileUpload {
  file: File;
  name: string;
  size: number;
  type: string;
}

/**
 * Response from chat endpoint.
 * Mirrors backend: backend/app/models/chat.py::ChatResponse
 */
export interface ChatResponse {
  success: boolean;
  session_id: string;
  response_type: string;
  message?: string;
  content?: string;
  intent?: IntentClassification;
  clarification?: ClarificationResponse;
  target_agent?: string;
  agent_result?: Record<string, unknown>;
  processing_time_seconds: number;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

/**
 * A single streaming event.
 * Mirrors backend: backend/app/models/chat.py::ChatStreamEvent
 */
export interface ChatStreamEvent {
  event_type: StreamEventType;
  session_id: string;
  data: StreamEventData;
  timestamp: string;
}

/**
 * Data payload for different stream event types.
 */
export interface StreamEventData {
  // Progress event data
  stage?: string;
  message?: string;
  progress_percent?: number;
  [key: string]: unknown;
}

/**
 * Progress update for streaming responses.
 * Mirrors backend: backend/app/models/chat.py::ProgressUpdate
 */
export interface ProgressUpdate {
  stage: string;
  message: string;
  progress_percent: number;
  metadata?: Record<string, unknown>;
}

/**
 * Conversation history for a session.
 * Mirrors backend: backend/app/models/chat.py::ConversationHistory
 */
export interface ConversationHistory {
  session_id: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
  summary?: string;
  current_intent?: UserIntent;
  pending_actions?: string[];
}

/**
 * Conversation summary.
 * Mirrors backend: backend/app/models/chat.py::ConversationSummary
 */
export interface ConversationSummary {
  summary: string;
  key_points: string[];
  current_intent?: string;
  pending_actions: string[];
}

/**
 * Agent capabilities response.
 * Mirrors backend: backend/app/models/chat.py::AgentCapabilities
 */
export interface AgentCapabilities {
  intents: UserIntent[];
  agents: string[];
  features: string[];
}

/**
 * Health status response.
 * Mirrors backend: backend/app/models/chat.py::HealthStatus
 */
export interface HealthStatus {
  success: boolean;
  status: string;
  agent: string;
  role: string;
  model: string;
  state: string;
  timestamp: string;
}

/**
 * Standard error response.
 * Mirrors backend: backend/app/models/chat.py::ErrorResponse
 */
export interface ErrorResponse {
  success: false;
  error: string;
  error_type: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

// ============================================================================
// FRONTEND-SPECIFIC TYPES
// ============================================================================

/**
 * UI state for the chat interface.
 */
export interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  isStreaming: boolean;
  currentProgress: ProgressUpdate | null;
  error: string | null;
  isAttested: boolean;
}

/**
 * Props for message bubble component.
 */
export interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

/**
 * Props for input area component.
 */
export interface InputAreaProps {
  onSend: (message: string, files?: FileUpload[]) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
}

/**
 * Scope attestation confirmation data.
 */
export interface ScopeAttestation {
  authorized: boolean;
  scope?: string;
  timestamp?: string;
}

// ============================================================================
// TYPE GUARDS
// ============================================================================

/**
 * Check if response is an error response.
 */
export function isErrorResponse(response: unknown): response is ErrorResponse {
  return (
    typeof response === "object" &&
    response !== null &&
    "success" in response &&
    (response as ErrorResponse).success === false
  );
}

/**
 * Check if stream event is a progress event.
 */
export function isProgressEvent(event: ChatStreamEvent): boolean {
  return event.event_type === StreamEventType.PROGRESS;
}

/**
 * Check if stream event is a result event.
 */
export function isResultEvent(event: ChatStreamEvent): boolean {
  return event.event_type === StreamEventType.RESULT;
}

/**
 * Check if stream event is an error event.
 */
export function isErrorEvent(event: ChatStreamEvent): boolean {
  return event.event_type === StreamEventType.ERROR;
}

/**
 * Check if stream event is the done event.
 */
export function isDoneEvent(event: ChatStreamEvent): boolean {
  return event.event_type === StreamEventType.DONE;
}
