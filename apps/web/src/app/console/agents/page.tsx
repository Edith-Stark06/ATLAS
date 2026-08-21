import { Bot, KeyRound, ShieldAlert, ShieldCheck } from "lucide-react";

import { LifecycleBadge, trustColor } from "@/components/ui/lifecycle-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { ApiError } from "@/components/ui/api-error";
import { fetchAgents, tryFetch } from "@/lib/api";
import { cn, formatTime } from "@/lib/utils";

export const metadata = { title: "Agent Registry — ATLAS" };
export const dynamic = "force-dynamic";

const COLUMNS = [
  "Agent Identity",
  "Owner / Domain",
  "Trust / Trend",
  "Model / Audit",
  "Last Decision",
  "Status",
];

export default async function AgentRegistryPage() {
  const result = await tryFetch(fetchAgents);

  if (!result.ok) {
    return (
      <>
        <PageHeader
          title="Agent"
          highlight="Registry"
          description="Inventory of registered autonomous entities, each carrying a continuously evaluated trust state."
        />
        <ApiError error={result.error} />
      </>
    );
  }

  const AGENTS = result.data;
  const trusted = AGENTS.filter((a) => a.lifecycle === "trusted").length;
  const needsAttention = AGENTS.filter(
    (a) => a.lifecycle === "review" || a.lifecycle === "anomaly",
  ).length;
  const totalDecisions = AGENTS.reduce((sum, a) => sum + a.decisionsToday, 0);

  return (
    <>
      <PageHeader
        title="Agent"
        highlight="Registry"
        description={`Complete inventory of ${AGENTS.length} registered autonomous entities, each carrying a continuously evaluated trust state.`}
      />

      <div className="mb-stack-md grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Registered Agents" value={String(AGENTS.length)} icon={Bot} tone="secondary" />
        <StatCard label="Trusted Tier" value={String(trusted)} icon={ShieldCheck} tone="tertiary" />
        <StatCard label="Needs Attention" value={String(needsAttention)} icon={ShieldAlert} tone="error" />
        <StatCard
          label="Decisions Today"
          value={totalDecisions.toLocaleString("en-US")}
          icon={KeyRound}
          tone="primary"
        />
      </div>

      <Panel>
        <PanelHeader
          title="Registered Agents"
          description="Trust scores recompute continuously; lifecycle state reflects the latest evaluation."
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse">
            <thead>
              <tr className="border-b border-white/5">
                {COLUMNS.map((col) => (
                  <th
                    key={col}
                    scope="col"
                    className="px-6 py-3 text-left font-mono text-status-label uppercase text-on-surface-variant"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {AGENTS.map((agent) => (
                <tr key={agent.id} className="transition-colors hover:bg-surface-variant/20">
                  <td className="px-6 py-4">
                    <p className="text-body-md text-on-surface">{agent.name}</p>
                    <p className="font-mono text-status-label text-outline">
                      {agent.id.toUpperCase()}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-body-sm text-on-surface-variant">{agent.owner}</p>
                    <p className="font-mono text-status-label text-outline">{agent.capability}</p>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-baseline gap-1">
                      <span className={cn("text-headline-sm", trustColor(agent.trustScore))}>
                        {agent.trustScore}
                      </span>
                      <span className="font-mono text-status-label text-outline">/100</span>
                    </div>
                    <p
                      className={cn(
                        "font-mono text-status-label",
                        agent.trustDelta >= 0 ? "text-tertiary" : "text-error",
                      )}
                    >
                      {agent.trustDelta >= 0 ? "▲" : "▼"} {Math.abs(agent.trustDelta).toFixed(1)} pts
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <p className="font-mono text-body-sm text-on-surface-variant">{agent.model}</p>
                    <p className="font-mono text-status-label text-outline">
                      Audit {agent.lastAuditAt} · Lvl {agent.authorityLevel}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-body-sm text-on-surface-variant">{agent.lastDecision}</p>
                    <p className="font-mono text-status-label text-outline">
                      {formatTime(agent.lastActiveAt)}
                    </p>
                  </td>
                  <td className="px-6 py-4">
                    <LifecycleBadge state={agent.lifecycle} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
