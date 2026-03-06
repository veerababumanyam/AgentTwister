# Frontend Assets

This directory contains all static assets for the AgentTwister frontend application.

## Directory Structure

```
assets/
├── Logo.png                    # Original source logo (830x830)
├── Fulllogo.png               # Full logo with text
├── Logo-removebg-preview.png  # Logo with transparent background
└── icons/
    ├── favicon.ico            # Multi-resolution favicon (16x16, 32x32, 48x48)
    ├── apple-touch-icon.png   # Apple touch icon (180x180)
    ├── logo-16.png            # 16x16 - inline use
    ├── logo-24.png            # 24x24 - toolbar icons
    ├── logo-32.png            # 32x32 - standard icons
    ├── logo-48.png            # 48x48 - medium icons
    ├── logo-64.png            # 64x64 - navigation, headers
    ├── logo-72.png            # 72x72 - mobile UI
    ├── logo-128.png           # 128x128 - large UI elements
    ├── logo-144.png           # 144x144 - Microsoft tiles
    ├── logo-192.png           # 192x192 - PWA, high-DPI
    ├── logo-256.png           # 256x256 - splash screens
    └── logo-512.png           # 512x512 - marketing, social
```

## Usage

### In TypeScript/React

```tsx
import { Logo } from "@/components/Logo";
import { LOGO_ASSETS, getLogoBySize } from "@/assets";

// Using the Logo component (recommended)
<Logo size={64} alt="AgentTwister" />

// Using direct asset paths
<img src={LOGO_ASSETS.x64} alt="AgentTwister" />

// Dynamic sizing
<img src={getLogoBySize(50)} alt="AgentTwister" />
```

### In HTML/Markdown

```html
<!-- Standard icon -->
<img src="/assets/icons/logo-32.png" width="32" height="32" alt="AgentTwister" />

<!-- High-resolution -->
<img src="/assets/icons/logo-192.png" width="192" height="192" alt="AgentTwister" />
```

## Asset Guidelines

### Size Selection Guide

| Use Case | Recommended Size |
|----------|------------------|
| Browser favicon | 16px, 32px (use favicon.ico) |
| Inline text | 16px |
| Toolbar buttons | 24px |
| Standard icons | 32px |
| Sidebar navigation | 48px |
| Headers/Navigation | 64px |
| Mobile UI | 72px |
| Cards/Modals | 128px |
| PWA/Mobile | 192px |
| Splash screens | 256px |
| Marketing/Social | 512px |

### Regenerating Assets

If you need to regenerate the logo sizes from the source:

```bash
cd frontend/assets

# Generate all sizes
magick Logo.png -resize 16x16 icons/logo-16.png
magick Logo.png -resize 24x24 icons/logo-24.png
magick Logo.png -resize 32x32 icons/logo-32.png
magick Logo.png -resize 48x48 icons/logo-48.png
magick Logo.png -resize 64x64 icons/logo-64.png
magick Logo.png -resize 72x72 icons/logo-72.png
magick Logo.png -resize 128x128 icons/logo-128.png
magick Logo.png -resize 144x144 icons/logo-144.png
magick Logo.png -resize 180x180 icons/apple-touch-icon.png
magick Logo.png -resize 192x192 icons/logo-192.png
magick Logo.png -resize 256x256 icons/logo-256.png
magick Logo.png -resize 512x512 icons/logo-512.png

# Generate favicon (multi-resolution ICO)
magick logo-16.png logo-32.png logo-48.png icons/favicon.ico
```

## PWA Configuration

The `public/manifest.json` file configures the Progressive Web App settings including icon references. The manifest supports:

- Installable PWA on mobile and desktop
- Proper icons for Android Chrome
- Apple touch icon for iOS
- Microsoft tile configuration for Windows

## Related Files

- `public/index.html` - HTML meta tags for all platforms
- `public/manifest.json` - PWA manifest
- `public/browserconfig.xml` - Microsoft browser configuration
- `src/assets/index.ts` - TypeScript asset module
- `src/components/Logo.tsx` - React Logo component
