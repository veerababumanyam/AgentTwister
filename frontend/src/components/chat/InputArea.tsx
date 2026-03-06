/**
 * InputArea Component
 *
 * Message input with file upload support.
 * Handles text input, file selection, and send action.
 */

"use client";

import React, { useState, useRef, KeyboardEvent, ClipboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { cn, formatFileSize } from "@/lib/utils";
import { Send, Paperclip, X } from "lucide-react";

export interface InputAreaProps {
  onSend: (message: string, files?: File[]) => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
  className?: string;
  maxLength?: number;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export function InputArea({
  onSend,
  disabled = false,
  isStreaming = false,
  placeholder = "Type your message...",
  className,
  maxLength = 10000,
}: InputAreaProps) {
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /**
   * Handle send button click.
   */
  const handleSend = () => {
    if (!message.trim() && files.length === 0) return;
    if (disabled || isStreaming) return;

    onSend(message.trim(), files);
    setMessage("");
    setFiles([]);
  };

  /**
   * Handle keyboard shortcuts.
   */
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter without Shift
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /**
   * Handle file selection.
   */
  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;

    const newFiles: File[] = [];

    for (const file of Array.from(selectedFiles)) {
      // Validate file size
      if (file.size > MAX_FILE_SIZE) {
        alert(`File "${file.name}" exceeds ${formatFileSize(MAX_FILE_SIZE)} limit`);
        continue;
      }
      newFiles.push(file);
    }

    setFiles((prev) => [...prev, ...newFiles]);
  };

  /**
   * Remove a file from the list.
   */
  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  /**
   * Handle drag events.
   */
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  /**
   * Handle paste events.
   */
  const handlePaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const pastedFiles = e.clipboardData?.files;
    if (pastedFiles && pastedFiles.length > 0) {
      e.preventDefault();
      handleFileSelect(pastedFiles);
    }
  };

  /**
   * Auto-resize textarea.
   */
  React.useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, [message]);

  const canSend = (message.trim().length > 0 || files.length > 0) && !disabled && !isStreaming;

  return (
    <div className={cn("border-t border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-900", className)}>
      {/* File previews */}
      {files.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="flex items-center gap-2 rounded-md bg-gray-100 px-3 py-1.5 text-sm dark:bg-gray-800"
            >
              <Paperclip className="h-3 w-3 text-gray-500" />
              <span className="max-w-[200px] truncate">{file.name}</span>
              <span className="text-xs text-gray-500">({formatFileSize(file.size)})</span>
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="ml-1 rounded-full p-0.5 hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                <X className="h-3 w-3 text-gray-500" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input container */}
      <div
        className={cn(
          "flex items-end gap-2 rounded-xl border-2 border-transparent bg-gray-100 p-2 transition-colors",
          isDragging && "border-primary-500 bg-primary-50 dark:bg-primary-900/20",
          "focus-within:border-primary-500 focus-within:bg-white dark:focus-within:bg-gray-800",
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* File upload button */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || isStreaming}
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors",
            "text-gray-500 hover:bg-gray-200 hover:text-gray-700",
            "dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200",
            "disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-gray-500",
          )}
          title="Attach files (max 10MB)"
        >
          <Paperclip className="h-5 w-5" />
        </button>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => handleFileSelect(e.target.files)}
        />

        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled || isStreaming}
          placeholder={files.length > 0 ? "" : placeholder}
          maxLength={maxLength}
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent py-2 text-sm text-gray-900 placeholder-gray-400",
            "focus:outline-none disabled:opacity-50 dark:text-gray-100 dark:placeholder-gray-500",
            "max-h-[200px] min-h-[40px]",
          )}
        />

        {/* Character count (when close to limit) */}
        {message.length > maxLength * 0.9 && (
          <span className="absolute bottom-1 right-14 text-xs text-gray-400">
            {message.length}/{maxLength}
          </span>
        )}

        {/* Send button */}
        <Button
          onClick={handleSend}
          disabled={!canSend}
          variant="primary"
          size="sm"
          className="h-10 px-4"
        >
          {isStreaming ? (
            <span className="flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Stop
            </span>
          ) : (
            <>
              <Send className="h-4 w-4" />
              <span className="sr-only">Send</span>
            </>
          )}
        </Button>
      </div>

      {/* Hint text */}
      <p className="mt-2 text-xs text-gray-500">
        Press <kbd className="rounded bg-gray-200 px-1 py-0.5 dark:bg-gray-700">Enter</kbd> to send,{" "}
        <kbd className="rounded bg-gray-200 px-1 py-0.5 dark:bg-gray-700">Shift + Enter</kbd> for new line.
        Drag & drop files or paste to attach.
      </p>
    </div>
  );
}

export default InputArea;
