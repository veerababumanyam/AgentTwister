/**
 * Root Layout
 *
 * Main layout component for the Next.js app.
 * Includes global styles and metadata.
 */

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AgentTwister - AI-Powered Security Research",
  description: "Ethical red-teaming tool for LLM-powered applications",
  manifest: "/manifest.json",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#030712" },
  ],
  viewport: "width=device-width, initial-scale=1, maximum-scale=1",
  icons: {
    icon: "/assets/icons/favicon.ico",
    apple: "/assets/icons/apple-touch-icon.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>{children}</body>
    </html>
  );
}
