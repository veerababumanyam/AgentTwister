/**
 * useChat Hook
 *
 * Main React hook for managing chat state and interactions.
 * Handles message sending, streaming responses, and conversation history.
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import type {
  ChatMessage,
  ChatState,
  ChatStreamEvent,
  ProgressUpdate,
  FileUpload,
  IntentClassification,
} from "@/types";
import { MessageType, UserIntent } from "@/types";
import { api, APIError } from "@/lib/api";

const SESSION_STORAGE_KEY = "agenttwister_session_id";
const ATTESTATION_KEY = "agenttwister_attested";

/**
 * Get or create a session ID from localStorage.
 */
function getSessionId(): string {
  if (typeof window === "undefined") return "";
  const stored = localStorage.getItem(SESSION_STORAGE_KEY);
  if (stored) return stored;
  const newId = crypto.randomUUID();
  localStorage.setItem(SESSION_STORAGE_KEY, newId);
  return newId;
}

/**
 * Check if user has attested to the scope.
 */
function getAttestationStatus(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(ATTESTATION_KEY) === "true";
}

/**
 * Set attestation status.
 */
function setAttestationStatus(attested: boolean): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ATTESTATION_KEY, attested.toString());
}

/**
 * Clear session data.
 */
export function clearSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(SESSION_STORAGE_KEY);
  localStorage.removeItem(ATTESTATION_KEY);
}

/**
 * Main chat hook for managing chat state and interactions.
 *
 * @example
 * ```tsx
 * const { messages, sendMessage, isStreaming, currentProgress } = useChat();
 * ```
 */
export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    sessionId: getSessionId(),
    isStreaming: false,
    currentProgress: null,
    error: null,
    isAttested: getAttestationStatus(),
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * Handle incoming stream events.
   */
  const handleStreamEvent = useCallback((event: ChatStreamEvent, messages: ChatMessage[]) => {
    switch (event.event_type) {
      case "progress": {
        const { stage, message, progress_percent } = event.data;
        setState((prev) => ({
          ...prev,
          currentProgress: {
            stage: stage as string || "",
            message: message as string || "",
            progress_percent: (progress_percent as number) ?? 0,
          },
        }));
        break;
      }
      case "message": {
        const newMessage: ChatMessage = {
          id: crypto.randomUUID(),
          type: MessageType.ASSISTANT,
          content: event.data.message as string || "",
          timestamp: event.timestamp,
        };
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, newMessage],
        }));
        break;
      }
      case "result": {
        // Final result from the agent
        const result = event.data;
        const assistantMessage: ChatMessage = {
          id: crypto.randomUUID(),
          type: MessageType.ASSISTANT,
          content: result.message as string || result.content as string || "",
          timestamp: event.timestamp,
          intent: result.intent ? (result.intent as IntentClassification).intent as UserIntent : undefined,
          confidence: result.intent ? (result.intent as IntentClassification).confidence : undefined,
          metadata: result,
        };
        setState((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
          isStreaming: false,
          currentProgress: null,
        }));
        break;
      }
      case "error": {
        setState((prev) => ({
          ...prev,
          error: event.data.error as string || "An error occurred",
          isStreaming: false,
          currentProgress: null,
        }));
        break;
      }
      case "done": {
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          currentProgress: null,
        }));
        break;
      }
    }
  }, []);

  /**
   * Send a message with optional file attachments.
   */
  const sendMessage = useCallback(
    async (content: string, files?: FileUpload[]) => {
      if (!content.trim() && (!files || files.length === 0)) return;

      // Check attestation
      if (!state.isAttested) {
        setState((prev) => ({
          ...prev,
          error: "Please confirm you are authorized to use this tool.",
        }));
        return;
      }

      // Add user message
      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        type: MessageType.USER,
        content: content.trim(),
        timestamp: new Date().toISOString(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
        isStreaming: true,
        error: null,
      }));

      // Abort any existing request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      abortControllerRef.current = new AbortController();

      try {
        // Validate files
        if (files) {
          for (const { file } of files) {
            if (file.size > 10 * 1024 * 1024) {
              throw new Error(`File "${file.name}" exceeds 10MB limit`);
            }
          }
        }

        // Stream the response
        const messages = [...state.messages, userMessage];
        for await (const event of api.streamMessage({
          message: content,
          session_id: state.sessionId || undefined,
          stream: true,
        })) {
          if (abortControllerRef.current.signal.aborted) break;
          handleStreamEvent(event, messages);
        }
      } catch (error) {
        if (error instanceof APIError) {
          setState((prev) => ({
            ...prev,
            error: error.message,
            isStreaming: false,
            currentProgress: null,
          }));
        } else if (error instanceof Error && error.name !== "AbortError") {
          setState((prev) => ({
            ...prev,
            error: error.message,
            isStreaming: false,
            currentProgress: null,
          }));
        }
      } finally {
        abortControllerRef.current = null;
      }
    },
    [state.messages, state.sessionId, state.isAttested, handleStreamEvent],
  );

  /**
   * Confirm scope attestation.
   */
  const attestToScope = useCallback((): void => {
    setAttestationStatus(true);
    setState((prev) => ({
      ...prev,
      isAttested: true,
      error: null,
    }));
  }, []);

  /**
   * Clear error state.
   */
  const clearError = useCallback((): void => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  /**
   * Reset chat state (start new conversation).
   */
  const resetChat = useCallback((): void => {
    clearSession();
    setState({
      messages: [],
      sessionId: getSessionId(),
      isStreaming: false,
      currentProgress: null,
      error: null,
      isAttested: getAttestationStatus(),
    });
  }, []);

  /**
   * Retry the last message.
   */
  const retryLastMessage = useCallback((): void => {
    const lastUserMessage = [...state.messages]
      .reverse()
      .find((m) => m.type === MessageType.USER);

    if (lastUserMessage) {
      // Remove messages after and including the last user message
      const lastUserIndex = state.messages.findIndex((m) => m.id === lastUserMessage.id);
      const previousMessages = state.messages.slice(0, lastUserIndex);

      setState((prev) => ({
        ...prev,
        messages: previousMessages,
        error: null,
      }));

      // Resend the message
      sendMessage(lastUserMessage.content);
    }
  }, [state.messages, sendMessage]);

  /**
   * Stop the current streaming response.
   */
  const stopStreaming = useCallback((): void => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState((prev) => ({
      ...prev,
      isStreaming: false,
      currentProgress: null,
    }));
  }, []);

  return {
    // State
    messages: state.messages,
    sessionId: state.sessionId,
    isStreaming: state.isStreaming,
    currentProgress: state.currentProgress,
    error: state.error,
    isAttested: state.isAttested,

    // Actions
    sendMessage,
    attestToScope,
    clearError,
    resetChat,
    retryLastMessage,
    stopStreaming,
  };
}

/**
 * Type for the return value of useChat.
 */
export type UseChatReturn = ReturnType<typeof useChat>;
