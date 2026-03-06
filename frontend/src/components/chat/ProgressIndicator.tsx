/**
 * ProgressIndicator Component
 *
 * Shows real-time progress updates during agent processing.
 * Displays the current stage and progress bar.
 */

"use client";

import React from "react";
import type { ProgressUpdate as ProgressUpdateType } from "@/types";
import { cn } from "@/lib/utils";
import { Loader2, CheckCircle2 } from "lucide-react";

export interface ProgressIndicatorProps {
  progress: ProgressUpdateType | null;
  className?: string;
}

/**
 * Get display color for progress stage.
 */
function getStageColor(stage: string): string {
  const stageLower = stage.toLowerCase();

  if (stageLower.includes("classify") || stageLower.includes("analyzing")) {
    return "bg-blue-500";
  }
  if (stageLower.includes("route") || stageLower.includes("planning")) {
    return "bg-purple-500";
  }
  if (stageLower.includes("generat") || stageLower.includes("payload")) {
    return "bg-orange-500";
  }
  if (stageLower.includes("validat") || stageLower.includes("verif")) {
    return "bg-green-500";
  }
  if (stageLower.includes("error") || stageLower.includes("failed")) {
    return "bg-red-500";
  }

  return "bg-primary-500";
}

/**
 * Get display icon for progress stage.
 */
function getStageIcon(stage: string): React.ReactNode {
  const stageLower = stage.toLowerCase();

  if (stageLower.includes("done") || stageLower.includes("complete")) {
    return <CheckCircle2 className="h-4 w-4 text-green-500" />;
  }

  return <Loader2 className="h-4 w-4 animate-spin text-primary-500" />;
}

export function ProgressIndicator({ progress, className }: ProgressIndicatorProps) {
  if (!progress) return null;

  const { stage, message, progress_percent } = progress;
  const percent = Math.round(progress_percent * 100);
  const barColor = getStageColor(stage);
  const icon = getStageIcon(stage);

  return (
    <div
      className={cn(
        "w-full rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-800/50",
        "animate-fade-in",
        className,
      )}
    >
      {/* Header with stage and icon */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {stage}
          </span>
        </div>
        <span className="text-xs text-gray-500 dark:text-gray-400">{percent}%</span>
      </div>

      {/* Progress message */}
      {message && (
        <p className="mb-2 text-xs text-gray-600 dark:text-gray-400">{message}</p>
      )}

      {/* Progress bar */}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className={cn("h-full rounded-full transition-all duration-300 ease-out", barColor)}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export default ProgressIndicator;
