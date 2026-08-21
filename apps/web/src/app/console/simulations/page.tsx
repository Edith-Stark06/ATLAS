import { BadgeCheck, FlaskConical, Inbox, TriangleAlert } from "lucide-react";

import { ScenarioWorkspace } from "@/components/simulation/scenario-workspace";
import { trustColor } from "@/components/ui/lifecycle-badge";
import { OutcomeBadge, riskColor } from "@/components/ui/outcome-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Pipeline } from "@/components/ui/pipeline";
import { StatusChip } from "@/components/ui/status-chip";
import { ApiError } from "@/components/ui/api-error";
import { fetchAgents, fetchSimulations, tryFetch } from "@/lib/api";
import type { SimulationOutcome } from "@/lib/types";
import { cn, formatPercent, formatTime, formatUsd } from "@/lib/utils";

export const metadata = { title: "Simulation Engine — ATLAS" };
export const dynamic = "force-dynamic";

const EXECUTION_STAGES = [
  { key: "request", label: "Agent Request", status: "done" as const },
  { key: "trust", label: "Trust Engine", status: "done" as const },
  { key: "simulation", label: "Simulation Engine", status: "active" as const },
  { key: "decision", label: "Decision Logic", status: "pending" as const },
  { key: "ledger", label: "Gov. Ledger", status: "pending" as const },
];

const QUALITATIVE_TONE: Record<string, string> = {
  High: "text-tertiary",
  Good: "text-tertiary",
  Poor: "text-error",
  Safe: "text-tertiary",
  Medium: "text-brand-amber",
};

function ScenarioCard({ outcome, index }: { outcome: SimulationOutcome; index: number }) {
  const letter = String.fromCharCode(65 + index);

  return (
    <div
      className={cn(
        "relative flex flex-col rounded-lg border p-5",
        outcome.recommended
          ? "border-tertiary/50 bg-tertiary/5 shadow-[0_0_16px_-6px_var(--color-tertiary)]"
          : "border-white/8 bg-surface-container-high/40",
      )}
    >
      {outcome.recommended && (
        <span className="absolute -top-2.5 left-5">
          <StatusChip tone="success">Recommended</StatusChip>
        </span>
      )}

      <div className="mb-4 flex items-baseline justify-between">
        <span className="font-mono text-label-mono uppercase text-on-surface-variant">
          Scenario {letter}
        </span>
        {outcome.compliant ? (
          <BadgeCheck className="size-4 text-tertiary" />
        ) : (
          <TriangleAlert className="size-4 text-brand-amber" />
        )}
      </div>

      <p className="mb-1 text-headline-sm text-on-surface">{outcome.label}</p>

      <div className="mb-4 flex items-baseline gap-2">
        <span className="text-headline-lg text-primary">
          {formatPercent(outcome.probability)}
        </span>
        <span className="font-mono text-label-mono text-outline">probability</span>
      </div>

      <div className="mb-4 h-1 w-full overflow-hidden rounded-full bg-surface-container-highest">
        <div
          className={cn("h-full rounded-full", outcome.recommended ? "bg-tertiary" : "bg-primary")}
          style={{ width: `${outcome.probability * 100}%` }}
        />
      </div>

      <dl className="mt-auto flex flex-col gap-2 border-t border-white/5 pt-3">
        {outcome.customerExperience && (
          <div className="flex justify-between">
            <dt className="text-body-sm text-on-surface-variant">Customer Exp.</dt>
            <dd className={cn("font-mono text-body-sm", QUALITATIVE_TONE[outcome.customerExperience])}>
              {outcome.customerExperience}
            </dd>
          </div>
        )}
        {outcome.complianceRisk && (
          <div className="flex justify-between">
            <dt className="text-body-sm text-on-surface-variant">Compliance Risk</dt>
            <dd className={cn("font-mono text-body-sm", QUALITATIVE_TONE[outcome.complianceRisk])}>
              {outcome.complianceRisk}
            </dd>
          </div>
        )}
        <div className="flex justify-between">
          <dt className="text-body-sm text-on-surface-variant">Risk Score</dt>
          <dd className={cn("font-mono text-body-sm", riskColor(outcome.riskScore))}>
            {outcome.riskScore}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-body-sm text-on-surface-variant">Financial Impact</dt>
          <dd className="font-mono text-body-sm text-on-surface">
            {formatUsd(outcome.financialImpactUsd)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export default async function SimulationsPage() {
  const [result, agentsResult] = await Promise.all([
    tryFetch(fetchSimulations),
    tryFetch(fetchAgents),
  ]);

  const workspace = agentsResult.ok && agentsResult.data.length > 0 && (
    <section className="mb-stack-md">
      <ScenarioWorkspace agents={agentsResult.data} />
    </section>
  );

  if (!result.ok || result.data.length === 0) {
    return (
      <>
        <PageHeader
          title="Simulation"
          highlight="Engine"
          description="Every autonomous financial decision is simulated before execution to predict downstream consequences."
        />
        {workspace}
        <ApiError error={result.ok ? "No simulation runs recorded yet." : result.error} />
      </>
    );
  }

  const [active, ...history] = result.data;

  const summary = [
    { label: "Agent", value: active.agentName },
    { label: "Amount", value: formatUsd(active.amountUsd) },
    { label: "Trust Score", value: String(active.trustScore), tone: trustColor(active.trustScore) },
    { label: "Confidence", value: `${active.confidence}%` },
    { label: "Runtime", value: `${active.durationMs}ms` },
  ];

  return (
    <>
      <PageHeader
        title="Simulation"
        highlight="Engine"
        description="Every autonomous financial decision is simulated before execution to predict downstream consequences."
      />

      {workspace}

      <h2 className="mb-4 text-headline-md text-on-surface">Last recorded run</h2>

      <Panel className="mb-stack-md">
        <PanelHeader
          title={active.scenario}
          icon={FlaskConical}
          // These are completed runs read back from the ledger, not live ones —
          // say what the simulation concluded rather than claiming it is running.
          action={<OutcomeBadge outcome={active.recommendation} />}
        />
        <dl className="grid grid-cols-2 divide-white/5 md:grid-cols-5 md:divide-x">
          {summary.map((item) => (
            <div key={item.label} className="px-6 py-4">
              <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                {item.label}
              </dt>
              <dd className={cn("mt-1 font-mono text-body-md text-on-surface", item.tone)}>
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
      </Panel>

      <div className="mb-stack-md grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="xl:col-span-4">
          <Panel className="h-full">
            <PanelHeader title="Incoming Request" icon={Inbox} />
            <dl className="divide-y divide-white/5">
              {active.request.map((row) => (
                <div key={row.label} className="flex items-center justify-between px-6 py-3">
                  <dt className="text-body-sm text-on-surface-variant">{row.label}</dt>
                  <dd className="font-mono text-body-sm text-on-surface">{row.value}</dd>
                </div>
              ))}
            </dl>
          </Panel>
        </div>

        <div className="xl:col-span-8">
          <Panel className="h-full">
            <PanelHeader
              title="Execution Pipeline"
              description="Simulation runs before the decision is committed."
            />
            <div className="p-6">
              <Pipeline stages={EXECUTION_STAGES} />
            </div>
          </Panel>
        </div>
      </div>

      <section className="mb-stack-md">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-headline-md text-on-surface">
            Predicting {active.outcomes.length === 3 ? "Three" : "Multiple"} Futures
          </h2>
          <span className="font-mono text-label-mono text-outline">
            Model-backed · {active.durationMs}ms
          </span>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {active.outcomes.map((outcome, i) => (
            <ScenarioCard key={outcome.label} outcome={outcome} index={i} />
          ))}
        </div>
      </section>

      <Panel>
        <PanelHeader title="Recent Simulation Runs" />
        <ul className="divide-y divide-white/5">
          {history.map((run) => (
            <li key={run.id} className="flex flex-wrap items-center gap-4 px-6 py-4">
              <span className="font-mono text-body-sm text-on-surface">{run.id}</span>
              <span className="min-w-0 flex-1 truncate text-body-sm text-on-surface-variant">
                {run.scenario}
              </span>
              <span className="font-mono text-status-label text-outline">
                {run.durationMs}ms · {formatTime(run.ranAt)}
              </span>
              <OutcomeBadge outcome={run.recommendation} />
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
