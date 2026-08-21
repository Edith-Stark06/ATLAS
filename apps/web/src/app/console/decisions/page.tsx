import Link from "next/link";
import { ChevronRight, CircleCheck, CircleSlash, Clock, TriangleAlert } from "lucide-react";

import { trustColor } from "@/components/ui/lifecycle-badge";
import { OutcomeBadge, riskColor } from "@/components/ui/outcome-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { ApiError } from "@/components/ui/api-error";
import { fetchDecisions, tryFetch } from "@/lib/api";
import { cn, formatTime, formatUsd } from "@/lib/utils";

export const metadata = { title: "Decision Intelligence — ATLAS" };
export const dynamic = "force-dynamic";

export default async function DecisionsPage() {
  const result = await tryFetch(fetchDecisions);

  if (!result.ok) {
    return (
      <>
        <PageHeader
          title="Decision"
          highlight="Intelligence"
          description="Every autonomous action that passed through the governance pipeline."
        />
        <ApiError error={result.error} />
      </>
    );
  }

  const DECISIONS = result.data;
  const approved = DECISIONS.filter((d) => d.outcome === "approved").length;
  const escalated = DECISIONS.filter((d) => d.outcome === "escalated").length;
  const blocked = DECISIONS.filter((d) => d.outcome === "blocked").length;
  const avgLatency = DECISIONS.length
    ? Math.round(DECISIONS.reduce((sum, d) => sum + d.latencyMs, 0) / DECISIONS.length)
    : 0;

  return (
    <>
      <PageHeader
        title="Decision"
        highlight="Intelligence"
        description="Every autonomous action that passed through the governance pipeline, with the trust state and policy evidence behind each verdict."
      />

      <div className="mb-stack-md grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Approved" value={String(approved)} icon={CircleCheck} tone="tertiary" />
        <StatCard label="Escalated" value={String(escalated)} icon={TriangleAlert} tone="error" />
        <StatCard label="Blocked" value={String(blocked)} icon={CircleSlash} tone="error" />
        <StatCard label="Avg Latency" value={`${avgLatency}ms`} icon={Clock} tone="secondary" />
      </div>

      <Panel>
        <PanelHeader
          title="Recent Decisions"
          description="Select a decision to open its full investigation trace."
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[940px] border-collapse">
            <thead>
              <tr className="border-b border-white/5">
                {["Decision", "Agent", "Amount", "Trust", "Risk", "Policies", "Outcome", ""].map(
                  (col, i) => (
                    <th
                      key={col || `col-${i}`}
                      scope="col"
                      className="px-6 py-3 text-left font-mono text-status-label uppercase text-on-surface-variant"
                    >
                      {col}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {DECISIONS.map((decision) => {
                const failed = decision.policyChecks.filter((c) => !c.passed).length;
                return (
                  <tr key={decision.id} className="group transition-colors hover:bg-surface-variant/20">
                    <td className="px-6 py-4">
                      <Link href={`/console/decisions/${decision.id}`} className="block">
                        <p className="font-mono text-body-sm text-on-surface group-hover:text-primary">
                          {decision.id}
                        </p>
                        <p className="max-w-[22ch] truncate text-status-label text-outline">
                          {decision.action}
                        </p>
                      </Link>
                    </td>
                    <td className="px-6 py-4 text-body-sm text-on-surface-variant">
                      {decision.agentName}
                    </td>
                    <td className="px-6 py-4 font-mono text-body-sm text-on-surface">
                      {formatUsd(decision.amountUsd)}
                    </td>
                    <td className={cn("px-6 py-4 font-mono text-body-sm", trustColor(decision.trustScore))}>
                      {decision.trustScore}
                    </td>
                    <td className={cn("px-6 py-4 font-mono text-body-sm", riskColor(decision.riskScore))}>
                      {decision.riskScore}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={cn(
                          "font-mono text-body-sm",
                          failed > 0 ? "text-error" : "text-tertiary",
                        )}
                      >
                        {decision.policyChecks.length - failed}/{decision.policyChecks.length}
                      </span>
                      <span className="ml-2 font-mono text-status-label text-outline">
                        {formatTime(decision.decidedAt)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <OutcomeBadge outcome={decision.outcome} />
                    </td>
                    <td className="px-6 py-4">
                      <Link
                        href={`/console/decisions/${decision.id}`}
                        aria-label={`Investigate ${decision.id}`}
                        className="text-outline transition-colors hover:text-primary"
                      >
                        <ChevronRight className="size-4" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
