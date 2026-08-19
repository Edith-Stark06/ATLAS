import { PlugZap } from "lucide-react";

import { Panel } from "@/components/ui/panel";

/** Shown when the backend is unreachable, instead of crashing the route. */
export function ApiError({ error }: { error: string }) {
  return (
    <Panel className="max-w-2xl">
      <div className="flex flex-col items-start gap-4 p-8">
        <span className="flex size-12 items-center justify-center rounded-lg border border-error/30 bg-error/10">
          <PlugZap className="size-6 text-error" />
        </span>
        <div>
          <h2 className="text-headline-sm text-on-surface">Backend unavailable</h2>
          <p className="mt-2 max-w-prose text-body-sm text-on-surface-variant">
            This screen reads live data from the ATLAS API, which did not respond.
          </p>
          <p className="mt-3 rounded border border-white/5 bg-surface-container-high/60 px-3 py-2 font-mono text-status-label text-error">
            {error}
          </p>
        </div>
        <div className="text-body-sm text-on-surface-variant">
          <p className="mb-1">Start the stack with:</p>
          <code className="font-mono text-status-label text-primary">
            npm run db:up
          </code>
          <span className="mx-2 text-outline">then</span>
          <code className="font-mono text-status-label text-primary">
            cd apps/api &amp;&amp; .venv/Scripts/python.exe -m app
          </code>
        </div>
      </div>
    </Panel>
  );
}
