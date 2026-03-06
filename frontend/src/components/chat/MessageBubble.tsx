/**
 * MessageBubble Component
 *
 * Displays a single chat message with appropriate styling.
 * Handles user, assistant, system, and progress message types.
 */

"use client";

import React from "react";
import type { ChatMessage as ChatMessageType } from "@/types";
import { MessageType, UserIntent } from "@/types";
import { cn, formatTimestamp } from "@/lib/utils";
import { Bot, User, AlertTriangle, Loader2 } from "lucide-react";

export interface MessageBubbleProps {
  message: ChatMessageType;
  isStreaming?: boolean;
  className?: string;
}

/**
 * Get intent display name.
 */
function getIntentLabel(intent?: UserIntent): string | null {
  if (!intent) return null;
  return intent
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * Get intent color class.
 */
function getIntentColor(intent?: UserIntent): string {
  if (!intent) return "text-gray-500";

  const colors: Record<UserIntent, string> = {
    [UserIntent.SECURITY_ANALYSIS]: "text-blue-500",
    [UserIntent.VULNERABILITY_SCAN]: "text-purple-500",
    [UserIntent.THREAT_MODELING]: "text-indigo-500",
    [UserIntent.PAYLOAD_GENERATION]: "text-orange-500",
    [UserIntent.PAYLOAD_CUSTOMIZATION]: "text-amber-500",
    [UserIntent.ATTACK_SIMULATION]: "text-red-500",
    [UserIntent.CAMPAIGN_PLANNING]: "text-cyan-500",
    [UserIntent.TEST_STRATEGY]: "text-teal-500",
    [UserIntent.SCOPE_DEFINITION]: "text-emerald-500",
    [UserIntent.DOCUMENT_UPLOAD]: "text-gray-500",
    [UserIntent.DOCUMENT_ANALYSIS]: "text-slate-500",
    [UserIntent.REPORT_GENERATION]: "text-violet-500",
    [UserIntent.SYSTEM_HELP]: "text-gray-400",
    [UserIntent.GENERAL_QUESTION]: "text-gray-400",
    [UserIntent.STATUS_CHECK]: "text-gray-400",
    [UserIntent.CLARIFICATION_NEEDED]: "text-yellow-500",
  };

  return colors[intent] || "text-gray-500";
}

export function MessageBubble({ message, isStreaming = false, className }: MessageBubbleProps) {
  const isUser = message.type === MessageType.USER;
  const isSystem = message.type === MessageType.SYSTEM;
  const isProgress = message.type === MessageType.PROGRESS;

  // Progress message with animated indicator
  if (isProgress) {
    return (
      <div className={cn("flex w-full justify-center py-2", className)}>
        <div className="flex items-center gap-2 rounded-full bg-primary-50 px-4 py-2 text-sm text-primary-700 dark:bg-primary-900/20 dark:text-primary-300">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>{message.content}</span>
        </div>
      </div>
    );
  }

  // System message
  if (isSystem) {
    return (
      <div className={cn("flex w-full justify-center py-2", className)}>
        <div className="flex items-center gap-2 rounded-md bg-gray-100 px-3 py-1.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
          <AlertTriangle className="h-3 w-3" />
          <span>{message.content}</span>
        </div>
      </div>
    );
  }

  // User message
  if (isUser) {
    return (
      <div className={cn("flex w-full justify-end", className)}>
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-primary-600 px-4 py-2.5 text-sm text-white dark:bg-primary-500">
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
          <span className="mt-1 block text-xs text-primary-200 opacity-70">
            {formatTimestamp(message.timestamp)}
          </span>
        </div>
      </div>
    );
  }

  // Assistant message
  const intentLabel = getIntentLabel(message.intent);
  const intentColor = getIntentColor(message.intent);

  return (
    <div className={cn("flex w-full justify-start", className)}>
      <div className="flex max-w-[80%] gap-3">
        {/* Avatar */}
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-primary-700 text-white shadow-sm">
          <Bot className="h-4 w-4" />
        </div>

        {/* Message content */}
        <div className="flex-1">
          {/* Intent label if present */}
          {intentLabel && (
            <div className={cn("mb-1 text-xs font-medium", intentColor)}>
              {intentLabel}
              {message.confidence !== undefined && (
                <span className="ml-1 text-gray-400">
                  ({Math.round(message.confidence * 100)}%)
                </span>
              )}
            </div>
          )}

          {/* Message bubble */}
          <div
            className={cn(
              "rounded-2xl rounded-bl-md px-4 py-2.5 text-sm",
              "bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100",
              isStreaming && "animate-pulse",
            )}
          >
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
            <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
              {formatTimestamp(message.timestamp)}
            </span>
          </div>

          {/* Tool calls if present */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="mt-2 space-y-1">
              {message.tool_calls.map((tool) => (
                <div
                  key={tool.id}
                  className="flex items-center gap-2 rounded-md bg-gray-50 px-2 py-1 text-xs text-gray-600 dark:bg-gray-800/50 dark:text-gray-400"
                >
                  <span className="font-mono">→ {tool.name}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default MessageBubble;
