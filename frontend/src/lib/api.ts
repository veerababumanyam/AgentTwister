/**
 * API Client
 *
 * HTTP client for communicating with the AgentTwister backend API.
 * Provides typed methods for all chat endpoints.
 */

import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  IntentClassification,
  ConversationHistory,
  ConversationSummary,
  AgentCapabilities,
  HealthStatus,
  ErrorResponse,
  FileUpload,
} from "@/types";

// ============================================================================
// CONFIGURATION
// ============================================================================

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const CHAT_BASE = `${API_BASE_URL}/api/v1/chat`;

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB in bytes
const DEFAULT_TIMEOUT = 30000; // 30 seconds
const STREAM_TIMEOUT = 120000; // 2 minutes for streaming

// ============================================================================
// ERROR HANDLING
// ============================================================================

export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public details?: unknown,
  ) {
    super(message);
    this.name = "APIError";
  }
}

export class TimeoutError extends APIError {
  constructor(message: string = "Request timed out") {
    super(message, 408);
    this.name = "TimeoutError";
  }
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Create an AbortController with a timeout.
 */
function createTimeoutController(timeoutMs: number): AbortController {
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeoutMs);
  return controller;
}

/**
 * Validate file size (max 10MB).
 */
export function validateFileSize(file: File): void {
  if (file.size > MAX_FILE_SIZE) {
    throw new Error(
      `File "${file.name}" exceeds maximum size of ${MAX_FILE_SIZE / 1024 / 1024}MB`,
    );
  }
}

/**
 * Convert files to FormData for upload.
 */
async function filesToFormData(files: FileUpload[]): Promise<FormData> {
  const formData = new FormData();
  for (const { file, name } of files) {
    validateFileSize(file);
    formData.append("files", file, name);
  }
  return formData;
}

/**
 * Handle fetch response with error checking.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData: ErrorResponse;
    try {
      errorData = await response.json();
    } catch {
      throw new APIError(
        `HTTP ${response.status}: ${response.statusText}`,
        response.status,
      );
    }
    throw new APIError(errorData.error || "Unknown error", response.status, errorData.details);
  }
  return response.json() as Promise<T>;
}

// ============================================================================
// API CLIENT
// ============================================================================

class APIClient {
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
    this.defaultHeaders = {
      "Content-Type": "application/json",
    };
  }

  /**
   * Send a chat message (non-streaming).
   */
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const controller = createTimeoutController(DEFAULT_TIMEOUT);

    try {
      const response = await fetch(`${CHAT_BASE}/`, {
        method: "POST",
        headers: this.defaultHeaders,
        body: JSON.stringify({
          message: request.message,
          session_id: request.session_id,
          stream: false,
          context: request.context,
        }),
        signal: controller.signal,
      });

      return handleResponse<ChatResponse>(response);
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        throw new TimeoutError("Chat request timed out");
      }
      throw error;
    }
  }

  /**
   * Send a chat message with streaming response via Server-Sent Events.
   * Returns an async iterator of stream events.
   */
  async *streamMessage(request: ChatRequest): AsyncGenerator<ChatStreamEvent> {
    const response = await fetch(`${CHAT_BASE}/stream`, {
      method: "POST",
      headers: this.defaultHeaders,
      body: JSON.stringify({
        message: request.message,
        session_id: request.session_id,
        stream: true,
        context: request.context,
      }),
    });

    if (!response.ok) {
      throw new APIError(`Stream failed: ${response.statusText}`, response.status);
    }

    if (!response.body) {
      throw new APIError("Response body is null");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            const eventLine = line.slice(6).trim();
            continue;
          }
          if (line.startsWith("data:")) {
            const data = line.slice(5).trim();
            if (data) {
              try {
                const event = JSON.parse(data) as ChatStreamEvent;
                yield event;
              } catch (e) {
                console.error("Failed to parse stream event:", e);
              }
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Classify intent without executing actions.
   */
  async classifyIntent(message: string, sessionId?: string): Promise<IntentClassification> {
    const response = await fetch(`${CHAT_BASE}/classify`, {
      method: "POST",
      headers: this.defaultHeaders,
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
    });

    const data = await handleResponse<{ success: boolean; classification: IntentClassification }>(
      response,
    );
    return data.classification;
  }

  /**
   * Get conversation session info.
   */
  async getSession(sessionId: string, includeSummary = false): Promise<ConversationHistory> {
    const params = new URLSearchParams({
      include_summary: includeSummary.toString(),
    });

    const response = await fetch(`${CHAT_BASE}/session/${sessionId}?${params}`, {
      method: "GET",
      headers: this.defaultHeaders,
    });

    return handleResponse<ConversationHistory>(response);
  }

  /**
   * Delete a conversation session.
   */
  async deleteSession(sessionId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${CHAT_BASE}/session/${sessionId}`, {
      method: "DELETE",
      headers: this.defaultHeaders,
    });

    return handleResponse(response);
  }

  /**
   * List all active sessions.
   */
  async listSessions(limit = 50, offset = 0): Promise<{
    success: boolean;
    total: number;
    sessions: ConversationHistory[];
  }> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

    const response = await fetch(`${CHAT_BASE}/sessions?${params}`, {
      method: "GET",
      headers: this.defaultHeaders,
    });

    return handleResponse(response);
  }

  /**
   * Generate conversation summary.
   */
  async generateSummary(sessionId: string): Promise<ConversationSummary> {
    const response = await fetch(`${CHAT_BASE}/session/${sessionId}/summary`, {
      method: "POST",
      headers: this.defaultHeaders,
    });

    const data = await handleResponse<{ success: boolean; summary: ConversationSummary }>(
      response,
    );
    return data.summary;
  }

  /**
   * Get agent capabilities.
   */
  async getCapabilities(): Promise<AgentCapabilities> {
    const response = await fetch(`${CHAT_BASE}/capabilities`, {
      method: "GET",
      headers: this.defaultHeaders,
    });

    return handleResponse<AgentCapabilities>(response);
  }

  /**
   * Health check for the chat orchestrator.
   */
  async healthCheck(): Promise<HealthStatus> {
    const response = await fetch(`${CHAT_BASE}/health`, {
      method: "GET",
      headers: this.defaultHeaders,
    });

    return handleResponse<HealthStatus>(response);
  }

  /**
   * Upload files (returns FormData for use with other requests).
   */
  async uploadFiles(files: FileUpload[]): Promise<void> {
    // Validate all files first
    for (const { file } of files) {
      validateFileSize(file);
    }

    // Files are sent with chat requests, not separately
    // This method validates files before sending
  }

  /**
   * Generate clarifying questions.
   */
  async generateClarification(
    message: string,
    classificationData?: Record<string, unknown>,
  ): Promise<{ clarification_needed: boolean; questions: string[]; context: string }> {
    const response = await fetch(`${CHAT_BASE}/clarify`, {
      method: "POST",
      headers: this.defaultHeaders,
      body: JSON.stringify({
        message,
        classification_data: classificationData,
      }),
    });

    const data = await handleResponse<{
      success: boolean;
      clarification: { clarification_needed: boolean; questions: string[]; context: string };
    }>(response);
    return data.clarification;
  }
}

// ============================================================================
// SINGLETON EXPORT
// ============================================================================

export const api = new APIClient();

export default api;
