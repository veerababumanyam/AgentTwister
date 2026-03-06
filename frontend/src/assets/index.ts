/**
 * Asset Module for AgentTwister Frontend
 *
 * This module provides centralized access to all static assets including
 * logos, icons, and images. Using a module approach allows for:
 *
 * 1. Type-safe asset references
 * 2. Easy updates when assets change
 * 3. Consistent asset paths across the application
 */

// ============================================================================
// Logo Assets
// ============================================================================

/**
 * Primary logo in various sizes
 * Use these for general UI elements like headers, navigation, etc.
 */
export const LOGO_ASSETS = {
  /** Very small - typically for inline use */
  x16: "/assets/icons/logo-16.png",
  /** Small - toolbar icons, small UI elements */
  x24: "/assets/icons/logo-24.png",
  /** Standard - common icon size */
  x32: "/assets/icons/logo-32.png",
  /** Medium - sidebar, navigation */
  x48: "/assets/icons/logo-48.png",
  /** Medium-large - toolbars, buttons */
  x64: "/assets/icons/logo-64.png",
  /** Large - mobile UI, cards */
  x72: "/assets/icons/logo-72.png",
  /** Large - headers, cards */
  x128: "/assets/icons/logo-128.png",
  /** Apple touch / PWA - standard mobile */
  x144: "/assets/icons/logo-144.png",
  /** High-DPI - retina displays, feature sections */
  x192: "/assets/icons/logo-192.png",
  /** Extra large - splash screens, loading states */
  x256: "/assets/icons/logo-256.png",
  /** Maximum - marketing, social sharing */
  x512: "/assets/icons/logo-512.png",
} as const;

/**
 * Get the appropriate logo size based on context
 * @param size - The desired size (width in pixels)
 * @returns The path to the logo asset
 */
export function getLogoBySize(size: number): string {
  if (size <= 16) return LOGO_ASSETS.x16;
  if (size <= 24) return LOGO_ASSETS.x24;
  if (size <= 32) return LOGO_ASSETS.x32;
  if (size <= 48) return LOGO_ASSETS.x48;
  if (size <= 64) return LOGO_ASSETS.x64;
  if (size <= 72) return LOGO_ASSETS.x72;
  if (size <= 128) return LOGO_ASSETS.x128;
  if (size <= 144) return LOGO_ASSETS.x144;
  if (size <= 192) return LOGO_ASSETS.x192;
  if (size <= 256) return LOGO_ASSETS.x256;
  return LOGO_ASSETS.x512;
}

/**
 * Original full-size logos
 */
export const FULL_LOGO = "/assets/Fulllogo.png";
export const LOGO_TRANSPARENT = "/assets/Logo-removebg-preview.png";
export const LOGO_ORIGINAL = "/assets/Logo.png";

// ============================================================================
// Favicon Assets
// ============================================================================

/**
 * Favicon - multi-resolution ICO format
 * Use in HTML: <link rel="icon" href={FAVICON} />
 */
export const FAVICON = "/assets/icons/favicon.ico";

/**
 * Apple Touch Icon - 180x180
 * Use in HTML: <link rel="apple-touch-icon" href={APPLE_TOUCH_ICON} />
 */
export const APPLE_TOUCH_ICON = "/assets/icons/apple-touch-icon.png";

// ============================================================================
// Asset Size Constants
// ============================================================================

/**
 * Standard sizes for different use cases
 * These follow common design patterns and device requirements
 */
export const ASSET_SIZES = {
  /** Favicon sizes (browser tabs) */
  FAVICON: {
    SMALL: 16,
    STANDARD: 32,
  },
  /** Touch icon sizes */
  TOUCH_ICON: {
    APPLE: 180,
    ANDROID: 192,
  },
  /** UI element sizes */
  UI: {
    INLINE: 16,
    SMALL: 24,
    STANDARD: 32,
    MEDIUM: 48,
    LARGE: 64,
    XLARGE: 128,
  },
  /** Feature/Hero section sizes */
  FEATURE: {
    STANDARD: 128,
    RETINA: 192,
    LARGE: 256,
    SPLASH: 512,
  },
} as const;

// ============================================================================
// Helper Types
// ============================================================================

/**
 * Size variants for logo components
 */
export type LogoSize = keyof typeof LOGO_ASSETS;

/**
 * Asset category types
 */
export type AssetCategory = "logo" | "favicon" | "touch-icon" | "full-logo";
