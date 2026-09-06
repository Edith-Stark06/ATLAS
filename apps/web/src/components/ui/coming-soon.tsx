import type { LucideIcon } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";

/**
 * Placeholder for sections that exist in the nav but have no screen yet.
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
      <PageHeader
        eyebrow="Roadmap"
        title={title}
        highlight={highlight}
        description={description}
        action={<StatusChip tone="brand">{phase}</StatusChip>}
      />
      <Panel className="max-w-2xl">
        <div className="flex flex-col items-start gap-4 px-4 py-4">
          <span className="flex size-9 items-center justify-center rounded-md border border-outline-variant bg-surface-container-high text-outline">
            <Icon className="size-4" strokeWidth={1.75} />
          </span>
          <p className="text-body-md text-on-surface-variant">
            This surface is part of the ATLAS governance pipeline but has not been built
            yet. It will cover:
          </p>
          <ul className="flex flex-col gap-2">
            {capabilities.map((item) => (
              <li
                key={item}
                className="flex items-start gap-2.5 text-body-md text-on-surface-variant"
              >
                <span className="mt-[7px] size-1 shrink-0 rounded-full bg-outline" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </Panel>
    </>
  );
}
