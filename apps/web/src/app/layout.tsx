import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ATLAS — AI Trust Operating System",
  description:
    "Adaptive Trust & Lifecycle Assurance System: a governance layer that decides whether autonomous financial agents can be trusted before they act.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    // Font variables live on <html> so they resolve at :root, where Tailwind
    // emits its --font-* theme values.
    <html lang="en" className={`dark ${inter.variable} ${geistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
