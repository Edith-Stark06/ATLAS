import { Unplug } from "lucide-react";

import { Panel } from "@/components/ui/panel";

/** Shown when the backend is unreachable, instead of crashing the route. */
export function ApiError({ error }: { error: string }) {
  return (
    <Panel className="max-w-2xl">
      <div className="flex flex-col items-start gap-4 px-4 py-4">
        <span className="flex size-9 items-center justify-center rounded-md border border-error/30 bg-error/[0.06] text-error">
          <Unplug className="size-4" strokeWidth={1.75} />
        </span>
        <div>
          <h2 className="text-headline-sm text-on-surface">Backend unavailable</h2>
          <p className="mt-1.5 max-w-prose text-body-md text-on-surface-variant">
            This screen reads live data from the ATLAS API, which did not respond.
          </p>
          <p className="mt-3 rounded-md border border-outline-variant bg-surface-container-high px-3 py-2 font-mono text-body-sm text-error">
            {error}
          </p>
        </div>
        <div className="text-body-sm text-on-surface-variant">
          <p className="mb-1.5">Start the stack with:</p>
          <code className="font-mono text-label-mono text-on-surface">npm run db:up</code>
          <span className="mx-2 text-outline">then</span>
          <code className="font-mono text-label-mono text-on-surface">
            cd apps/api &amp;&amp; .venv/Scripts/python.exe -m app
          </code>
        </div>
      </div>
    </Panel>
  );
}

/** Nothing to show, and that is not an error — say what would put data here. */
export function EmptyState({
  title,
  description,
  icon: Icon,
  action,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 px-6 py-10 text-center ${className ?? ""}`}
    >
      {Icon && (
        <span className="mb-1 flex size-9 items-center justify-center rounded-md border border-outline-variant bg-surface-container-high text-outline">
          <Icon className="size-4" strokeWidth={1.75} />
        </span>
      )}
      <p className="text-body-md text-on-surface">{title}</p>
      {description && (
        <p className="max-w-[46ch] text-body-sm text-on-surface-variant">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
