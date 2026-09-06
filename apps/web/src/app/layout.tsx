import type { Metadata } from "next";
import { Instrument_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

/**
 * Instrument Sans carries the whole interface — a grotesque with enough
 * character to belong to ATLAS rather than to every dashboard, and tabular
 * figures that keep dense columns from jittering.
 */
const instrument = Instrument_Sans({
  variable: "--font-instrument",
  subsets: ["latin"],
  display: "swap",
});

/** Identifiers, hashes, versions and thresholds. Never body text. */
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "ATLAS — Governance Control Plane",
  description:
    "ATLAS governs consequential autonomous actions: every request is evaluated against policy and trust, decided, and recorded in a verifiable governance ledger.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // Font variables live on <html> so they resolve at :root, where Tailwind
    // emits its --font-* theme values.
    <html lang="en" className={`dark ${instrument.variable} ${jetbrainsMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
