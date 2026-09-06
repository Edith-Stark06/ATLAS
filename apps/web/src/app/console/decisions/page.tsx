import Link from "next/link";
import { ChevronRight, CircleCheck, CircleSlash, Clock, TriangleAlert } from "lucide-react";

import { ExecutePanel } from "@/components/decisions/execute-panel";
import { ApiError, EmptyState } from "@/components/ui/api-error";
import { DataTable, type Column } from "@/components/ui/data-table";
import { trustColor } from "@/components/ui/lifecycle-badge";
import { OutcomeBadge, riskColor } from "@/components/ui/outcome-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { fetchAgents, fetchDecisions, tryFetch } from "@/lib/api";
import type { Decision } from "@/lib/types";
import { cn, formatTime, formatUsd } from "@/lib/utils";

export const metadata = { title: "Decisions — ATLAS" };
export const dynamic = "force-dynamic";

const COLUMNS: Column<Decision>[] = [
  {
    key: "decision",
    header: "Decision",
    width: "32%",
    cell: (decision) => (
      <>
        <p className="truncate text-body-md text-on-surface">{decision.action}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 font-mono text-label-mono-xs text-outline">
          {decision.id}
          {/* The agent gets its own column from `md` up. */}
          <span className="md:hidden">· {decision.agentName}</span>
        </p>
      </>
    ),
  },
  {
    key: "agent",
    header: "Agent",
    width: "17%",
    hideBelow: "md",
    cell: (decision) => (
      <span className="text-body-sm text-on-surface-variant">{decision.agentName}</span>
    ),
  },
  {
    key: "amount",
    header: "Impact",
    align: "right",
    width: "9%",
    cell: (decision) => (
      <span className="font-mono text-body-sm text-on-surface">
        {formatUsd(decision.amountUsd)}
      </span>
    ),
  },
  {
    key: "trust",
    header: "Trust",
    align: "right",
    width: "6%",
    hideBelow: "sm",
    cell: (decision) => (
      <span className={cn("font-mono text-body-sm", trustColor(decision.trustScore))}>
        {decision.trustScore}
      </span>
    ),
  },
  {
    key: "risk",
    header: "Risk",
    align: "right",
    width: "6%",
    hideBelow: "sm",
    cell: (decision) => (
      <span className={cn("font-mono text-body-sm", riskColor(decision.riskScore))}>
        {decision.riskScore}
      </span>
    ),
  },
  {
    key: "policies",
    header: "Policies",
    align: "right",
    width: "7%",
    hideBelow: "lg",
    cell: (decision) => {
      const failed = decision.policyChecks.filter((check) => !check.passed).length;
      return (
        <span
          className={cn(
            "font-mono text-body-sm",
            failed > 0 ? "text-error" : "text-on-surface-variant",
          )}
        >
          {decision.policyChecks.length - failed}/{decision.policyChecks.length}
        </span>
      );
    },
  },
  {
    key: "decided",
    header: "Decided",
    align: "right",
    width: "9%",
    hideBelow: "lg",
    cell: (decision) => (
      <span className="font-mono text-label-mono-xs text-outline">
        {formatTime(decision.decidedAt)}
      </span>
    ),
  },
  {
    key: "outcome",
    header: "Outcome",
    width: "10%",
    cell: (decision) => <OutcomeBadge outcome={decision.outcome} />,
  },
  {
    key: "open",
    header: <span className="sr-only">Open</span>,
    align: "right",
    width: "4%",
    cell: (decision) => (
      <Link
        href={`/console/decisions/${encodeURIComponent(decision.id)}`}
        aria-label={`Investigate ${decision.id}`}
        className="inline-flex text-outline transition-colors hover:text-primary"
      >
        <ChevronRight className="size-4" />
      </Link>
    ),
  },
];

export default async function DecisionsPage() {
  const [result, agentsResult] = await Promise.all([
    tryFetch(fetchDecisions),
    tryFetch(fetchAgents),
  ]);

  const header = (
    <PageHeader
      eyebrow="Mission Control"
      title="Decisions"
      description="Every autonomous action that passed through the governance pipeline, with the trust state and policy evidence behind each verdict."
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

  const decisions = result.data;
  const approved = decisions.filter((d) => d.outcome === "approved").length;
  const escalated = decisions.filter((d) => d.outcome === "escalated").length;
  const blocked = decisions.filter((d) => d.outcome === "blocked").length;
  const avgLatency = decisions.length
    ? Math.round(decisions.reduce((sum, d) => sum + d.latencyMs, 0) / decisions.length)
    : 0;

  return (
    <>
      {header}

      <div className="mb-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard
          label="Approved"
          value={String(approved)}
          icon={CircleCheck}
          tone="tertiary"
          hint={`of ${decisions.length}`}
        />
        <StatCard
          label="Escalated"
          value={String(escalated)}
          icon={TriangleAlert}
          tone="warning"
        />
        <StatCard label="Blocked" value={String(blocked)} icon={CircleSlash} tone="error" />
        <StatCard label="Median latency" value={`${avgLatency}ms`} icon={Clock} />
      </div>

      {agentsResult.ok && agentsResult.data.length > 0 && (
        <ExecutePanel agents={agentsResult.data} />
      )}

      <Panel>
        <PanelHeader
          title="Recent decisions"
          description="Select a decision to open its full investigation."
        />
        <DataTable
          columns={COLUMNS}
          rows={decisions}
          rowKey={(decision) => decision.id}
          onRowHref={(decision) => `/console/decisions/${encodeURIComponent(decision.id)}`}
          fixed
          minWidthClass="md:min-w-[66rem]"
          empty={
            <EmptyState
              title="No decisions recorded yet"
              description="Commit an action above and it will appear here with its full evidence trail."
            />
          }
        />
      </Panel>
    </>
  );
}
