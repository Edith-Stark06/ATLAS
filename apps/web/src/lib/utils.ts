import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Times are rendered in UTC with a fixed locale so the server and client
 * produce identical markup. Relative formatting ("2m ago") would depend on
 * "now" and mismatch during hydration.
 */
const TIME_FORMAT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
});

const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  timeZone: "UTC",
});

export function formatTime(iso: string): string {
  return `${TIME_FORMAT.format(new Date(iso))} UTC`;
}

export function formatDate(iso: string): string {
  return DATE_FORMAT.format(new Date(iso));
}

export function formatUsd(amount: number | null): string {
  if (amount === null) return "—";
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "−" : "";
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${sign}$${(abs / 1_000).toFixed(1)}K`;
  return `${sign}$${abs.toLocaleString("en-US")}`;
}

export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}
