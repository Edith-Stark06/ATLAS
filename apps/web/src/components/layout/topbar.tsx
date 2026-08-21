import { Bell, LogOut, UserRound } from "lucide-react";

import { getSession } from "@/lib/session";

const ROLE_TONE: Record<string, string> = {
  admin: "bg-error/10 text-error",
  operator: "bg-secondary/10 text-secondary",
  viewer: "bg-outline/10 text-on-surface-variant",
};

const ENVIRONMENT_FLAGS = [
  { label: "Production", tone: "text-cyan-glow", dot: "bg-cyan-glow", strong: true },
  { label: "Compliant", tone: "text-on-surface-variant", dot: "bg-tertiary-green", strong: false },
  { label: "Healthy", tone: "text-on-surface-variant", dot: "bg-tertiary-green", strong: false },
];

export async function Topbar() {
  const session = await getSession();

  return (
    <header className="sticky top-0 z-40 flex h-16 w-full items-center justify-between border-b border-white/5 bg-surface-container-low/50 px-gutter shadow-sm backdrop-blur-md">
      <div className="flex items-center gap-4">
        <span className="text-headline-sm font-bold text-on-surface">ATLAS Enterprise</span>
        <span className="h-4 w-px bg-outline-variant/50" />
        <div className="flex gap-4">
          {ENVIRONMENT_FLAGS.map((flag) => (
            <span
              key={flag.label}
              className={`flex items-center gap-1.5 font-mono text-label-mono ${flag.tone} ${
                flag.strong ? "font-bold" : ""
              }`}
            >
              <span className={`size-1.5 rounded-full ${flag.dot}`} />
              {flag.label}
            </span>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          aria-label="Alerts"
          className="relative rounded p-1.5 text-on-surface-variant transition-colors hover:text-on-surface"
        >
          <Bell className="size-5" />
          <span className="absolute right-1 top-1 size-1.5 rounded-full bg-error" />
        </button>
        {session && (
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-body-sm text-on-surface">{session.name}</p>
              <span
                className={`inline-flex rounded-xl px-2 py-0.5 text-status-label uppercase ${
                  ROLE_TONE[session.role] ?? ROLE_TONE.viewer
                }`}
              >
                {session.role}
              </span>
            </div>
            <span className="flex size-8 items-center justify-center rounded-full border border-white/10 bg-surface-container-high">
              <UserRound className="size-4 text-on-surface-variant" />
            </span>
            {/* A form POST, not a link: signing out is a state change, and a
                GET would let any page log the user out with an <img> tag. */}
            <form action="/api/auth/logout" method="post">
              <button
                type="submit"
                aria-label="Sign out"
                className="rounded p-1.5 text-on-surface-variant transition-colors hover:text-on-surface"
              >
                <LogOut className="size-4" />
              </button>
            </form>
          </div>
        )}
      </div>
    </header>
  );
}
