import type { LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";

/**
 * Placeholder for sections that exist in the nav but have no design yet.
 * Better than a 404, and honest about what is not built.
 */
export function ComingSoon({
  title,
  highlight,
  description,
  icon: Icon,
  phase,
  capabilities,
}: {
  title: string;
  highlight: string;
  description: string;
  icon: LucideIcon;
  phase: string;
  capabilities: string[];
}) {
  return (
    <>
      <PageHeader title={title} highlight={highlight} description={description} />
      <Panel className="max-w-3xl">
        <div className="flex flex-col items-start gap-5 p-8">
          <span className="flex size-12 items-center justify-center rounded-lg border border-primary/30 bg-primary/10">
            <Icon className="size-6 text-primary" />
          </span>
          <div>
            <p className="font-mono text-label-mono uppercase text-primary">{phase}</p>
            <p className="mt-2 text-body-md text-on-surface-variant">
              This surface is part of the ATLAS governance pipeline but has not been built yet.
              It will cover:
            </p>
          </div>
          <ul className="flex flex-col gap-2">
            {capabilities.map((item) => (
              <li key={item} className="flex items-start gap-2.5 text-body-sm text-on-surface-variant">
                <span className="mt-1.5 size-1 shrink-0 rounded-full bg-secondary" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </Panel>
    </>
  );
}
