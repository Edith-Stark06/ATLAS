import { ChevronRight, Boxes, ShieldAlert, ShieldCheck, Zap } from "lucide-react";
import Link from "next/link";

import { TrustDelta } from "@/components/console/agent-row";
import { ApiError, EmptyState } from "@/components/ui/api-error";
import { Meter } from "@/components/ui/charts";
import { DataTable, type Column } from "@/components/ui/data-table";
import { LifecycleBadge, trustColor, trustFill } from "@/components/ui/lifecycle-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { fetchAgents, tryFetch } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

export const metadata = { title: "Agent Registry — ATLAS" };
export const dynamic = "force-dynamic";

const COLUMNS: Column<Agent>[] = [
  {
    key: "agent",
    header: "Agent",
    width: "24%",
    cell: (agent) => (
      <>
        <p className="truncate text-body-md text-on-surface">{agent.name}</p>
        <p className="mt-0.5 font-mono text-label-mono-xs text-outline">{agent.id}</p>
        {/* Below `md` the Status column is dropped rather than squeezed — a
            truncated "ONBOARDIN…" chip says less than no chip at all — so the
            state rides along under the name instead. */}
        <span className="mt-1 inline-flex md:hidden">
          <LifecycleBadge state={agent.lifecycle} />
        </span>
      </>
    ),
  },
  {
    key: "domain",
    header: "Domain",
    width: "15%",
    hideBelow: "md",
    cell: (agent) => (
      <>
        <p className="truncate text-body-sm text-on-surface-variant">{agent.capability}</p>
        <p className="mt-0.5 truncate text-label-mono-xs text-outline">{agent.owner}</p>
      </>
    ),
  },
  {
    key: "trust",
    header: "Trust",
    width: "13%",
    cell: (agent) => (
      <div className="flex items-center gap-2.5">
        <Meter
          value={agent.trustScore}
          color={trustFill(agent.trustScore)}
          className="hidden w-16 shrink-0 lg:block"
        />
        <span className={cn("font-mono text-body-md", trustColor(agent.trustScore))}>
          {agent.trustScore}
        </span>
        <TrustDelta delta={agent.trustDelta} />
      </div>
    ),
  },
  {
    key: "authority",
    header: "Auth",
    align: "right",
    width: "5%",
    hideBelow: "xl",
    cell: (agent) => (
      <span className="font-mono text-body-sm text-on-surface-variant">
        L{agent.authorityLevel}
      </span>
    ),
  },
  {
    key: "model",
    header: "Model",
    width: "11%",
    hideBelow: "xl",
    cell: (agent) => (
      <>
        <p className="truncate font-mono text-label-mono text-on-surface-variant">
          {agent.model}
        </p>
        <p className="mt-0.5 truncate font-mono text-label-mono-xs text-outline">
          {agent.lastAuditAt}
        </p>
      </>
    ),
  },
  {
    key: "last",
    header: "Last action",
    width: "20%",
    hideBelow: "lg",
    cell: (agent) => (
      <>
        <p className="truncate text-body-sm text-on-surface-variant">{agent.lastDecision}</p>
        <p className="mt-0.5 font-mono text-label-mono-xs text-outline">
          {formatTime(agent.lastActiveAt)} · {agent.decisionsToday.toLocaleString("en-US")}{" "}
          today
        </p>
      </>
    ),
  },
  {
    key: "status",
    header: "Status",
    width: "8%",
    hideBelow: "md",
    cell: (agent) => <LifecycleBadge state={agent.lifecycle} />,
  },
  {
    key: "open",
    header: <span className="sr-only">Open</span>,
    align: "right",
    width: "4%",
    cell: (agent) => (
      <Link
        href={`/console/agents/${encodeURIComponent(agent.id)}`}
        aria-label={`Open ${agent.name}`}
        className="inline-flex text-outline transition-colors hover:text-primary"
      >
        <ChevronRight className="size-4" />
      </Link>
    ),
  },
];

export default async function AgentRegistryPage() {
  const result = await tryFetch(fetchAgents);

  const header = (
    <PageHeader
      eyebrow="Agents"
      title="Agent registry"
      description="Every registered autonomous entity, the job it does, and the trust state it currently carries."
    />
  );

  if (!result.ok) {
    return (
      <>
        {header}
        <ApiError error={result.error} />
      </>
    );
  }

  const agents = result.data;
  const trusted = agents.filter((agent) => agent.lifecycle === "trusted").length;
  const needsAttention = agents.filter(
    (agent) => agent.lifecycle === "review" || agent.lifecycle === "anomaly",
  ).length;
  const totalDecisions = agents.reduce((sum, agent) => sum + agent.decisionsToday, 0);

  return (
    <>
      {header}

      <div className="mb-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard label="Registered" value={String(agents.length)} icon={Boxes} />
        <StatCard
          label="Trusted Tier"
          value={String(trusted)}
          icon={ShieldCheck}
          tone="tertiary"
          hint={`of ${agents.length}`}
        />
        <StatCard
          label="Needs attention"
          value={String(needsAttention)}
          icon={ShieldAlert}
          tone={needsAttention > 0 ? "warning" : "tertiary"}
        />
        <StatCard
          label="Decisions today"
          value={totalDecisions.toLocaleString("en-US")}
          icon={Zap}
        />
      </div>

      <Panel>
        <PanelHeader
          title="Registered agents"
          description="Trust recomputes continuously; lifecycle state reflects the latest evaluation."
        />
        <DataTable
          columns={COLUMNS}
          rows={agents}
          rowKey={(agent) => agent.id}
          onRowHref={(agent) => `/console/agents/${encodeURIComponent(agent.id)}`}
          fixed
          minWidthClass="md:min-w-[72rem]"
          empty={<EmptyState title="No agents registered" />}
        />
      </Panel>
    </>
  );
}
