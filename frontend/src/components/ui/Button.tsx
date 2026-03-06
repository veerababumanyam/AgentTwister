/**
 * Button Component
 *
 * Reusable button component with variants and sizes.
 */

"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "outline";
  size?: "xs" | "sm" | "md" | "lg";
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles = {
  primary: cn(
    "bg-primary-600 text-white hover:bg-primary-700 focus:ring-primary-500",
    "disabled:bg-gray-300 disabled:text-gray-500",
    "dark:bg-primary-500 dark:hover:bg-primary-600 dark:disabled:bg-gray-700 dark:disabled:text-gray-500",
  ),
  secondary: cn(
    "bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500",
    "disabled:bg-gray-100 disabled:text-gray-400",
    "dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600 dark:disabled:bg-gray-800 dark:disabled:text-gray-500",
  ),
  ghost: cn(
    "bg-transparent text-gray-700 hover:bg-gray-100 focus:ring-gray-500",
    "disabled:text-gray-400",
    "dark:text-gray-300 dark:hover:bg-gray-800 dark:disabled:text-gray-600",
  ),
  danger: cn(
    "bg-danger-600 text-white hover:bg-danger-700 focus:ring-danger-500",
    "disabled:bg-gray-300 disabled:text-gray-500",
    "dark:bg-danger-500 dark:hover:bg-danger-600 dark:disabled:bg-gray-700 dark:disabled:text-gray-500",
  ),
  outline: cn(
    "border border-gray-300 bg-transparent text-gray-700 hover:bg-gray-50 focus:ring-gray-500",
    "disabled:border-gray-200 disabled:text-gray-400",
    "dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800 dark:disabled:border-gray-700 dark:disabled:text-gray-600",
  ),
};

const sizeStyles = {
  xs: "px-2 py-1 text-xs",
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

const iconSizeStyles = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-4 w-4",
  lg: "h-5 w-5",
};

export function Button({
  variant = "primary",
  size = "md",
  isLoading = false,
  leftIcon,
  rightIcon,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const iconSize = iconSizeStyles[size];

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium",
        "transition-colors duration-150",
        "focus:outline-none focus:ring-2 focus:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-60",
        variantStyles[variant],
        sizeStyles[size],
        className,
      )}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <span className={cn("animate-spin", iconSize)}>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            className="animate-spin"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        </span>
      ) : (
        <>
          {leftIcon && <span className={cn("shrink-0", iconSize)}>{leftIcon}</span>}
          {children}
          {rightIcon && <span className={cn("shrink-0", iconSize)}>{rightIcon}</span>}
        </>
      )}
    </button>
  );
}

export default Button;
