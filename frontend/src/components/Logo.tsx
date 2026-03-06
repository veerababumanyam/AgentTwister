/**
 * Logo Component
 *
 * A responsive logo component that automatically selects the appropriate
 * image size based on the display context. This follows responsive image
 * best practices and ensures optimal loading performance.
 *
 * Usage:
 * ```tsx
 * <Logo size={64} alt="AgentTwister" />
 * <Logo size="large" className="mr-2" />
 * ```
 */

import React from "react";
import { getLogoBySize, LOGO_ASSETS, FULL_LOGO, LOGO_TRANSPARENT } from "../assets";

export interface LogoProps {
  /** Alt text for accessibility */
  alt?: string;
  /** Size in pixels or predefined size name */
  size?: number | "small" | "medium" | "large" | "xlarge" | "full";
  /** Additional CSS classes */
  className?: string;
  /** Use the full logo with text */
  showFull?: boolean;
  /** Use the transparent background version */
  transparent?: boolean;
  /** Inline styles */
  style?: React.CSSProperties;
  /** Click handler */
  onClick?: () => void;
}

const SIZE_MAP = {
  small: 32,
  medium: 64,
  large: 128,
  xlarge: 256,
  full: 512,
} as const;

export function Logo({
  alt = "AgentTwister Logo",
  size = "medium",
  className = "",
  showFull = false,
  transparent = false,
  style,
  onClick,
}: LogoProps) {
  // Determine the pixel size
  const pixelSize = typeof size === "number" ? size : SIZE_MAP[size] || 64;

  // Select the appropriate source
  const src = showFull
    ? FULL_LOGO
    : transparent
    ? LOGO_TRANSPARENT
    : getLogoBySize(pixelSize);

  // Generate srcSet for responsive images (1x and 2x DPI)
  const srcSet =
    !showFull && !transparent
      ? `${getLogoBySize(pixelSize)} 1x, ${getLogoBySize(pixelSize * 2)} 2x`
      : undefined;

  return (
    <img
      src={src}
      srcSet={srcSet}
      alt={alt}
      width={pixelSize}
      height={pixelSize}
      className={className}
      style={{
        objectFit: "contain",
        ...style,
      }}
      onClick={onClick}
      role="img"
      aria-label={alt}
    />
  );
}

export default Logo;
