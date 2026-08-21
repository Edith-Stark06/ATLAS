import { Bell, UserRound } from "lucide-react";

const ENVIRONMENT_FLAGS = [
  { label: "Production", tone: "text-cyan-glow", dot: "bg-cyan-glow", strong: true },
  { label: "Compliant", tone: "text-on-surface-variant", dot: "bg-tertiary-green", strong: false },
  { label: "Healthy", tone: "text-on-surface-variant", dot: "bg-tertiary-green", strong: false },
];

export function Topbar() {
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
        <span className="flex size-8 items-center justify-center rounded-full border border-white/10 bg-surface-container-high">
          <UserRound className="size-4 text-on-surface-variant" />
        </span>
      </div>
    </header>
  );
}
