import { Activity } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { StatusPip, type PipTone } from "@/components/ui/status-pip";
import { API_BASE_URL, fetchHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

interface ServiceRow {
  name: string;
  detail: string;
  tone: PipTone;
  label: string;
}

function buildServiceRows(
  probe: Awaited<ReturnType<typeof fetchHealth>>,
): ServiceRow[] {
  const web: ServiceRow = {
    name: "web",
    detail: "next.js · app router",
    tone: "up",
    label: "UP",
  };

  if (!probe.reachable) {
    return [
      web,
      { name: "api", detail: probe.error, tone: "down", label: "UNREACHABLE" },
      {
        name: "postgres",
        detail: "not probed — api unreachable",
        tone: "idle",
        label: "UNKNOWN",
      },
    ];
  }

  return [
    web,
    {
      name: "api",
      detail: `fastapi · v${probe.data.version} · ${probe.data.environment}`,
      tone: "up",
      label: "UP",
    },
    ...probe.data.dependencies.map<ServiceRow>((dep) => ({
      name: dep.name,
      detail: dep.detail ?? "connection ok",
      tone: dep.status === "up" ? "up" : "down",
      label: dep.status.toUpperCase(),
    })),
  ];
}

export default async function StatusPage() {
  const probe = await fetchHealth();
  const services = buildServiceRows(probe);
  const allUp = services.every((s) => s.tone === "up");

  return (
    <>
      <PageHeader
        title="System"
        highlight="Status"
        description="Live health of the ATLAS stack, probed end to end from this page through the API to its data stores."
      />

      <Panel className="max-w-4xl">
        <PanelHeader
          title="Services"
          icon={Activity}
          action={
            <div className="flex items-center gap-2">
              <StatusPip tone={allUp ? "up" : "warn"} pulse />
              <span className="font-mono text-label-mono text-outline">{API_BASE_URL}</span>
            </div>
          }
        />
        <ul className="divide-y divide-white/5">
          {services.map((service) => (
            <li key={service.name} className="flex items-center gap-4 px-6 py-3.5">
              <StatusPip tone={service.tone} />
              <span className="w-24 shrink-0 font-mono text-body-sm text-on-surface">
                {service.name}
              </span>
              <span className="min-w-0 flex-1 truncate text-body-sm text-on-surface-variant">
                {service.detail}
              </span>
              <StatusChip
                tone={
                  service.tone === "up"
                    ? "success"
                    : service.tone === "down"
                      ? "danger"
                      : "neutral"
                }
              >
                {service.label}
              </StatusChip>
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
