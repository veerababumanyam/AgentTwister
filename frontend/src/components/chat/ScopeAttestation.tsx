/**
 * ScopeAttestation Component
 *
 * Modal for confirming scope attestation before using the tool.
 * Ensures users acknowledge they are authorized to perform security testing.
 */

"use client";

import React from "react";
import { Shield, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

export interface ScopeAttestationProps {
  onConfirm: () => void;
  className?: string;
}

export function ScopeAttestation({ onConfirm, className }: ScopeAttestationProps) {
  const [agreed, setAgreed] = React.useState(false);
  const [step, setStep] = React.useState<"read" | "confirm">("read");

  const handleContinue = () => {
    if (step === "read") {
      setStep("confirm");
    } else {
      onConfirm();
    }
  };

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4",
        "animate-fade-in",
        className,
      )}
    >
      <div
        className={cn(
          "w-full max-w-lg rounded-2xl bg-white shadow-xl dark:bg-gray-900",
          "animate-slide-up",
        )}
      >
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-100 dark:bg-primary-900/30">
            <Shield className="h-5 w-5 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Scope Attestation Required
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Please confirm before continuing
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {step === "read" ? (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-lg bg-amber-50 p-3 dark:bg-amber-900/20">
                <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
                <div className="text-sm">
                  <p className="font-medium text-amber-900 dark:text-amber-100">
                    Important Legal Notice
                  </p>
                  <p className="mt-1 text-amber-800 dark:text-amber-200">
                    AgentTwister is a security research tool for authorized testing only.
                    Unauthorized use is illegal.
                  </p>
                </div>
              </div>

              <div className="space-y-2 text-sm text-gray-700 dark:text-gray-300">
                <p className="font-medium">By using AgentTwister, you confirm that:</p>
                <ul className="ml-4 list-disc space-y-1">
                  <li>
                    You have explicit written authorization to test the target system(s)
                  </li>
                  <li>
                    Testing is conducted within defined scope boundaries
                  </li>
                  <li>
                    You will not exceed authorized access or impact system availability
                  </li>
                  <li>
                    All findings will be reported responsibly to the appropriate parties
                  </li>
                  <li>
                    Use complies with applicable laws (CFAA, Computer Misuse Act, etc.)
                  </li>
                </ul>
              </div>

              <div className="rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  <strong>Note:</strong> This tool is designed for authorized penetration
                  testing, security research, and red team exercises only.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-lg bg-primary-50 p-3 dark:bg-primary-900/20">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary-600 dark:text-primary-400" />
                <div className="text-sm">
                  <p className="font-medium text-primary-900 dark:text-primary-100">
                    Final Confirmation
                  </p>
                  <p className="mt-1 text-primary-800 dark:text-primary-200">
                    Please confirm your understanding and agreement.
                  </p>
                </div>
              </div>

              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-200 p-3 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800">
                <input
                  type="checkbox"
                  checked={agreed}
                  onChange={(e) => setAgreed(e.target.checked)}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  I confirm I have authorization to test the target system(s) and will use
                  this tool responsibly and legally.
                </span>
              </label>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700">
          <Button
            variant="outline"
            onClick={() => window.location.reload()}
            className="flex-1 sm:flex-none"
          >
            Decline
          </Button>
          <Button
            variant="primary"
            onClick={handleContinue}
            disabled={step === "confirm" && !agreed}
            className="flex-1 sm:flex-none"
          >
            {step === "read" ? "I Understand" : "Confirm & Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ScopeAttestation;
