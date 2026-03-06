/**
 * ChatInterface Component
 *
 * Main chat interface component that brings together all chat-related components.
 * Manages the message list, input area, and streaming state.
 */

"use client";

import React, { useEffect, useRef } from "react";
import { useChat } from "@/hooks/useChat";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { InputArea } from "@/components/chat/InputArea";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { ProgressIndicator } from "@/components/chat/ProgressIndicator";
import { ScopeAttestation } from "@/components/chat/ScopeAttestation";
import { Logo } from "@/components/Logo";
import { cn } from "@/lib/utils";
import {
  Menu,
  X,
  RotateCcw,
  Trash2,
  AlertTriangle,
} from "lucide-react";

export interface ChatInterfaceProps {
  className?: string;
}

export function ChatInterface({ className }: ChatInterfaceProps) {
  const {
    messages,
    isStreaming,
    currentProgress,
    error,
    isAttested,
    sendMessage,
    attestToScope,
    clearError,
    resetChat,
    stopStreaming,
  } = useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  /**
   * Auto-scroll to bottom when new messages arrive.
   */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentProgress]);

  /**
   * Handle send with file attachments.
   */
  const handleSend = (message: string, files?: File[]) => {
    if (files && files.length > 0) {
      // File uploads would be handled here
      // For now, just send the message
      sendMessage(message);
    } else {
      sendMessage(message);
    }
  };

  /**
   * Show attestation modal if not attested.
   */
  if (!isAttested) {
    return <ScopeAttestation onConfirm={attestToScope} />;
  }

  return (
    <div className={cn("flex h-screen flex-col bg-gray-50 dark:bg-gray-950", className)}>
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-800 lg:hidden"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <Logo size={32} />
          <div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              AgentTwister
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              AI-Powered Security Research
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Reset chat button */}
          <button
            type="button"
            onClick={resetChat}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-300"
            title="Start new conversation"
          >
            <RotateCcw className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar (session history) */}
        <aside
          className={cn(
            "absolute inset-y-0 left-0 z-40 w-64 transform border-r border-gray-200 bg-white transition-transform dark:border-gray-800 dark:bg-gray-900 lg:static lg:translate-x-0",
            sidebarOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex h-full flex-col">
            {/* Sidebar header */}
            <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-800">
              <h2 className="font-semibold text-gray-900 dark:text-gray-100">
                Conversations
              </h2>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                className="rounded-lg p-1 hover:bg-gray-100 dark:hover:bg-gray-800 lg:hidden"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Session list */}
            <div className="flex-1 overflow-y-auto p-2">
              <div className="rounded-lg bg-gray-100 p-3 text-center text-sm text-gray-500 dark:bg-gray-800 dark:text-gray-400">
                <p>Session history coming soon</p>
              </div>
            </div>

            {/* Sidebar footer */}
            <div className="border-t border-gray-200 p-4 dark:border-gray-800">
              <button
                type="button"
                onClick={resetChat}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                <Trash2 className="h-4 w-4" />
                Clear Current Session
              </button>
            </div>
          </div>
        </aside>

        {/* Overlay for mobile sidebar */}
        {sidebarOpen && (
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          />
        )}

        {/* Chat area */}
        <main className="flex flex-1 flex-col">
          {/* Messages container */}
          <div
            ref={messagesContainerRef}
            className="flex-1 overflow-y-auto px-4 py-6"
          >
            <div className="mx-auto max-w-3xl space-y-4">
              {/* Welcome message */}
              {messages.length === 0 && (
                <div className="text-center">
                  <div className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 text-white shadow-lg">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      className="h-8 w-8"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
                      />
                    </svg>
                  </div>
                  <h2 className="mb-2 text-2xl font-bold text-gray-900 dark:text-gray-100">
                    Welcome to AgentTwister
                  </h2>
                  <p className="mb-6 text-gray-600 dark:text-gray-400">
                    Your AI-powered security research assistant
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <button
                      type="button"
                      onClick={() => sendMessage("Analyze my chatbot for prompt injection vulnerabilities")}
                      className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition-colors hover:border-primary-500 hover:bg-primary-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-primary-500 dark:hover:bg-primary-900/20"
                    >
                      <span className="font-medium">Analyze for vulnerabilities</span>
                      <span className="block text-xs text-gray-500">
                        Test your LLM application
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => sendMessage("Generate a test payload for prompt injection")}
                      className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition-colors hover:border-primary-500 hover:bg-primary-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:border-primary-500 dark:hover:bg-primary-900/20"
                    >
                      <span className="font-medium">Generate test payload</span>
                      <span className="block text-xs text-gray-500">
                        Create adversarial prompts
                      </span>
                    </button>
                  </div>
                </div>
              )}

              {/* Messages */}
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}

              {/* Progress indicator */}
              {currentProgress && <ProgressIndicator progress={currentProgress} />}

              {/* Typing indicator */}
              {isStreaming && !currentProgress && <TypingIndicator />}

              {/* Error message */}
              {error && (
                <div className="flex items-center gap-3 rounded-lg bg-danger-50 p-4 text-sm text-danger-800 dark:bg-danger-900/20 dark:text-danger-200">
                  <AlertTriangle className="h-5 w-5 shrink-0 text-danger-600 dark:text-danger-400" />
                  <div className="flex-1">
                    <p className="font-medium">Error</p>
                    <p className="text-danger-700 dark:text-danger-300">{error}</p>
                  </div>
                  <button
                    type="button"
                    onClick={clearError}
                    className="shrink-0 rounded-lg p-1 hover:bg-danger-100 dark:hover:bg-danger-900/30"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}

              {/* Scroll anchor */}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input area */}
          <InputArea
            onSend={handleSend}
            disabled={isStreaming}
            isStreaming={isStreaming}
          />
        </main>
      </div>
    </div>
  );
}

export default ChatInterface;
