"use client";

import { usePathname } from "next/navigation";

import { resolveNavItem } from "@/lib/nav";

/**
 * `ATLAS / <section>` — the top bar states where you are and nothing else.
 * Telemetry belongs on the pages that can act on it.
 */
export function Breadcrumb() {
  const pathname = usePathname();
  const item = resolveNavItem(pathname);
  const label = item ? (item.breadcrumb ?? item.label) : "Console";

  return (
    <div className="flex min-w-0 items-baseline gap-2">
      <span className="text-body-sm font-semibold tracking-[0.12em] text-on-surface-variant">
        ATLAS
      </span>
      <span className="text-outline" aria-hidden>
        /
      </span>
      <span className="truncate text-body-sm font-medium text-on-surface">{label}</span>
    </div>
  );
}
