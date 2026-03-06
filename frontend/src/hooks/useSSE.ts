/**
 * useSSE Hook
 *
 * React hook for Server-Sent Events (SSE) streaming.
 * Provides a low-level interface for SSE connections.
 */

"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface SSEOptions {
  /**
   * Whether the connection should be active.
   */
  enabled?: boolean;

  /**
   * Timeout in milliseconds before considering the connection stale.
   */
  timeout?: number;

  /**
   * Function to call when a message is received.
   */
  onMessage?: (event: MessageEvent) => void;

  /**
   * Function to call when an error occurs.
   */
  onError?: (event: Event) => void;

  /**
   * Function to call when the connection opens.
   */
  onOpen?: (event: Event) => void;

  /**
   * Function to call when the connection closes.
   */
  onClose?: (event: Event) => void;

  /**
   * Whether to reconnect automatically on disconnect.
   */
  reconnect?: boolean;

  /**
   * Maximum number of reconnection attempts.
   */
  maxReconnectAttempts?: number;
}

export interface SSEState {
  /**
   * Whether the connection is currently active.
   */
  connected: boolean;

  /**
   * Whether a reconnection attempt is in progress.
   */
  reconnecting: boolean;

  /**
   * Number of reconnection attempts made.
   */
  reconnectAttempts: number;

  /**
   * Last error that occurred.
   */
  error: string | null;
}

/**
 * Hook for managing Server-Sent Events (SSE) connections.
 *
 * @example
 * ```tsx
 * const { connected, error } = useSSE("http://localhost:8000/stream", {
 *   onMessage: (event) => console.log(event.data),
 *   enabled: isActive,
 * });
 * ```
 */
export function useSSE(url: string | null, options: SSEOptions = {}) {
  const {
    enabled = true,
    timeout = 60000,
    onMessage,
    onError,
    onOpen,
    onClose,
    reconnect = true,
    maxReconnectAttempts = 5,
  } = options;

  const [state, setState] = useState<SSEState>({
    connected: false,
    reconnecting: false,
    reconnectAttempts: 0,
    error: null,
  });

  const eventSourceRef = useRef<EventSource | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  /**
   * Clear all timeouts.
   */
  const clearTimeouts = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  /**
   * Close the EventSource connection.
   */
  const close = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    clearTimeouts();
    if (mountedRef.current) {
      setState((prev) => ({ ...prev, connected: false, reconnecting: false }));
    }
  }, [clearTimeouts]);

  /**
   * Handle connection errors.
   */
  const handleError = useCallback(
    (event: Event) => {
      const errorData = (event as any]?.data as string) || "Connection error";

      if (mountedRef.current) {
        setState((prev) => ({ ...prev, error: errorData }));
      }

      onError?.(event);

      // Attempt reconnection if enabled and within max attempts
      if (reconnect && state.reconnectAttempts < maxReconnectAttempts) {
        if (mountedRef.current) {
          setState((prev) => ({
            ...prev,
            connected: false,
            reconnecting: true,
            reconnectAttempts: prev.reconnectAttempts + 1,
          }));
        }

        // Exponential backoff for reconnection
        const delay = Math.min(1000 * Math.pow(2, state.reconnectAttempts), 30000);
        reconnectTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current && url) {
            connect();
          }
        }, delay);
      } else {
        close();
        onClose?.(event);
      }
    },
    [reconnect, maxReconnectAttempts, state.reconnectAttempts, url, onError, onClose, close],
  );

  /**
   * Handle connection open.
   */
  const handleOpen = useCallback(
    (event: Event) => {
      if (mountedRef.current) {
        setState((prev) => ({
          ...prev,
          connected: true,
          reconnecting: false,
          reconnectAttempts: 0,
          error: null,
        }));
      }

      // Reset timeout on successful connection
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        if (eventSourceRef.current?.readyState === EventSource.OPEN) {
          // Connection is stale but not closed - refresh it
          close();
          if (url && mountedRef.current) {
            connect();
          }
        }
      }, timeout);

      onOpen?.(event);
    },
    [timeout, url, onOpen, close],
  );

  /**
   * Handle incoming message.
   */
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      // Reset timeout on message received
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => {
          if (eventSourceRef.current?.readyState === EventSource.OPEN) {
            close();
            if (url && mountedRef.current) {
              connect();
            }
          }
        }, timeout);
      }

      onMessage?.(event);
    },
    [timeout, url, onMessage, close],
  );

  /**
   * Establish SSE connection.
   */
  const connect = useCallback(() => {
    if (!url || !enabled || !mountedRef.current) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = handleOpen;
      eventSource.onmessage = handleMessage;
      eventSource.onerror = handleError;

      // Set initial state
      setState({
        connected: false,
        reconnecting: false,
        reconnectAttempts: 0,
        error: null,
      });
    } catch (error) {
      if (mountedRef.current) {
        setState((prev) => ({
          ...prev,
          error: error instanceof Error ? error.message : "Failed to connect",
        }));
      }
      onError?.(error as Event);
    }
  }, [url, enabled, handleOpen, handleMessage, handleError, onError]);

  /**
   * Connect on mount and when URL/enabled changes.
   */
  useEffect(() => {
    connect();

    return () => {
      mountedRef.current = false;
      close();
    };
  }, [connect, close]);

  /**
   * Manual reconnect function.
   */
  const reconnectManual = useCallback(() => {
    close();
    setState((prev) => ({ ...prev, reconnectAttempts: 0 }));
    setTimeout(() => connect(), 100);
  }, [close, connect]);

  return {
    ...state,
    reconnect: reconnectManual,
    close,
  };
}

/**
 * Hook for parsing SSE event stream data.
 *
 * @example
 * ```tsx
 * const parseEvent = useSSEParser();
 * const events = parseEvent(rawEventData);
 * ```
 */
export function useSSEParser() {
  const parseEvent = useCallback<T = unknown>(data: string): T | null => {
    try {
      // Handle "data: " prefix from SSE format
      const cleanData = data.replace(/^data:\s*/, "").trim();
      if (!cleanData) return null;
      return JSON.parse(cleanData) as T;
    } catch {
      return null;
    }
  }, []);

  return { parseEvent };
}
