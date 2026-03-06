/**
 * TypingIndicator Component
 *
 * Animated typing indicator shown when the assistant is generating a response.
 */

"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface TypingIndicatorProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

/**
 * Single dot animation component.
 */
function TypingDot({ delay }: { delay: number }) {
  return (
    <span
      className="inline-block h-2 w-2 animate-bounce rounded-full bg-current opacity-60"
      style={{
        animationDelay: `${delay}ms`,
        animationDuration: "600ms",
      }}
    />
  );
}

export function TypingIndicator({ className, size = "md" }: TypingIndicatorProps) {
  const sizeClasses = {
    sm: "h-6 w-12 text-xs",
    md: "h-8 w-16 text-sm",
    lg: "h-10 w-20 text-base",
  };

  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-2xl rounded-bl-md bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500",
        sizeClasses[size],
        className,
      )}
    >
      <span className="flex items-center gap-1">
        <TypingDot delay={0} />
        <TypingDot delay={150} />
        <TypingDot delay={300} />
      </span>
    </div>
  );
}

export default TypingIndicator;
