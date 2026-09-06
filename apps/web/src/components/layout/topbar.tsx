import Link from "next/link";
import { Bell, LogOut } from "lucide-react";

import { Breadcrumb } from "@/components/layout/breadcrumb";
import { CommandSearch } from "@/components/layout/command-search";
import { getSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const ROLE_TONE: Record<string, string> = {
  admin: "border-outline-strong text-on-surface-variant",
  operator: "border-outline-strong text-on-surface-variant",
  viewer: "border-outline-variant text-outline",
};

/** First letters of the signed-in name — no avatar service, no placeholder art. */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return (parts[0][0] + (parts[1]?.[0] ?? "")).toUpperCase();
}

export async function Topbar() {
  const session = await getSession();

  return (
    <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-outline-variant bg-surface-container-lowest px-4 lg:px-5">
      {/* Room for the mobile nav trigger, which is fixed at the same height. */}
      <div className="w-9 shrink-0 lg:hidden" aria-hidden />

      <Breadcrumb />

      <span
        className="ml-1 hidden shrink-0 items-center gap-1.5 rounded-md border border-outline-variant px-2 py-1 text-status-label uppercase text-on-surface-variant sm:inline-flex"
        title="Environment"
      >
        <span className="size-1.5 rounded-full bg-tertiary" aria-hidden />
        Production
      </span>

      <div className="ml-auto flex items-center gap-2">
        <div className="hidden md:block">
          <CommandSearch />
        </div>

        <Link
          href="/console/alerts"
          aria-label="Alerts"
          className="relative rounded-md p-2 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
        >
          <Bell className="size-4" strokeWidth={1.75} />
        </Link>

        {session && (
          <div className="flex items-center gap-2 border-l border-outline-variant pl-2">
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-md border border-outline-strong bg-surface-container-high text-label-mono-xs font-semibold text-on-surface-variant"
              title={session.email || session.name}
              aria-hidden
            >
              {initials(session.name)}
            </span>
            <div className="hidden leading-tight lg:block">
              <p className="max-w-[12ch] truncate text-body-sm text-on-surface">
                {session.name}
              </p>
              <span
                className={cn(
                  "inline-flex rounded-sm border px-1 text-status-label uppercase",
                  ROLE_TONE[session.role] ?? ROLE_TONE.viewer,
                )}
              >
                {session.role}
              </span>
            </div>
            {/* A form POST, not a link: signing out is a state change, and a
                GET would let any page log the user out with an <img> tag. */}
            <form action="/api/auth/logout" method="post">
              <button
                type="submit"
                aria-label="Sign out"
                className="rounded-md p-2 text-outline transition-colors hover:bg-surface-container-high hover:text-on-surface"
              >
                <LogOut className="size-4" strokeWidth={1.75} />
              </button>
            </form>
          </div>
        )}
      </div>
    </header>
  );
}
