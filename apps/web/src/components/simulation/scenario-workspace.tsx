"use client";

import { useState, useTransition } from "react";
import { BadgeCheck, Play, Scale, ShieldAlert, TriangleAlert } from "lucide-react";

import { OutcomeBadge, riskColor } from "@/components/ui/outcome-badge";
import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { runSimulation } from "@/lib/api-client";
import type {
  Agent,
  PredictedOutcome,
  RuleEffect,
  SimulateActionResponse,
} from "@/lib/types";
import { cn, formatPercent, formatUsd } from "@/lib/utils";

const FIELD_CLASS =
  "rounded border border-white/10 bg-surface-container-high px-2 py-1.5 font-mono text-body-sm text-on-surface focus:border-secondary focus:outline-none";

const EFFECT_LABELS: Record<RuleEffect, string> = {
  allow: "Allow",
  require_human_review: "Require review",
  block: "Block",
};

const EFFECT_TONE: Record<RuleEffect, "success" | "warning" | "danger"> = {
  allow: "success",
  require_human_review: "warning",
  block: "danger",
};

interface Scenario {
  agentId: string;
  action: string;
  amountUsd: string;
  riskScore: number;
  /** Empty means "use the agent's live trust score". */
  trustScore: string;
  hourUtc: string;
}

const DEFAULT_SCENARIO: Scenario = {
  agentId: "",
  action: "Approve vendor payment",
  amountUsd: "4820",
  riskScore: 45,
  trustScore: "",
  hourUtc: "",
};

function Labelled({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-mono text-status-label uppercase text-on-surface-variant">
        {label}
      </span>
      {children}
      {hint && <span className="text-body-sm text-outline">{hint}</span>}
    </label>
  );
}

/** The money story: what moves, what is held back, and what an unpoliced
 * system would have exposed. The third figure is the point of the product. */
function ExposureLedger({ result }: { result: SimulateActionResponse }) {
  const prevented = result.unconstrainedExposureUsd - result.expectedExposureUsd;

  const rows = [
    {
      label: "Moves if followed",
      value: formatUsd(result.expectedExposureUsd),
      tone: result.expectedExposureUsd > 0 ? "text-on-surface" : "text-tertiary",
    },
    { label: "Held back", value: formatUsd(result.withheldUsd), tone: "text-brand-amber" },
    {
      label: "Ungoverned estimate",
      value: formatUsd(result.unconstrainedExposureUsd),
      tone: "text-on-surface-variant",
    },
  ];

  return (
    <Panel interactive={false}>
      <PanelHeader
        title="Exposure"
        icon={Scale}
        description="Deterministic — money follows the recommendation, not the raw probabilities."
      />
      <dl className="divide-y divide-white/5">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between px-6 py-3">
            <dt className="text-body-sm text-on-surface-variant">{row.label}</dt>
            <dd className={cn("font-mono text-body-md", row.tone)}>{row.value}</dd>
          </div>
        ))}
      </dl>
      {prevented > 0.5 && (
        <p className="border-t border-white/5 px-6 py-3 text-body-sm text-on-surface-variant">
          Governance avoids{" "}
          <span className="font-mono text-tertiary">{formatUsd(prevented)}</span> of average
          exposure on this action.
        </p>
      )}
    </Panel>
  );
}

function OutcomeCard({ outcome }: { outcome: PredictedOutcome }) {
  return (
    <div
      className={cn(
        "relative flex flex-col rounded-lg border p-4",
        outcome.recommended
          ? "border-tertiary/50 bg-tertiary/5 shadow-[0_0_16px_-6px_var(--color-tertiary)]"
          : "border-white/8 bg-surface-container-high/40",
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <p className="text-body-md text-on-surface">{outcome.label}</p>
        {outcome.compliant ? (
          <BadgeCheck className="size-4 shrink-0 text-tertiary" />
        ) : (
          <TriangleAlert className="size-4 shrink-0 text-brand-amber" />
        )}
      </div>

      <div className="mb-3 flex items-baseline gap-2">
        <span className="text-headline-md text-primary">
          {formatPercent(outcome.probability)}
        </span>
        {outcome.recommended && <StatusChip tone="success">Recommended</StatusChip>}
      </div>

      <div className="mb-3 h-1 w-full overflow-hidden rounded-full bg-surface-container-highest">
        <div
          className={cn("h-full rounded-full", outcome.recommended ? "bg-tertiary" : "bg-primary")}
          style={{ width: `${outcome.probability * 100}%` }}
        />
      </div>

      <dl className="mt-auto flex flex-col gap-1.5 border-t border-white/5 pt-3">
        <div className="flex justify-between">
          <dt className="text-body-sm text-on-surface-variant">Residual risk</dt>
          <dd className={cn("font-mono text-body-sm", riskColor(outcome.riskScore))}>
            {outcome.riskScore}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-body-sm text-on-surface-variant">Money moved</dt>
          <dd className="font-mono text-body-sm text-on-surface">
            {formatUsd(outcome.financialImpactUsd)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function PolicyTrace({ result }: { result: SimulateActionResponse }) {
  // Rules that did not apply are still listed: showing only the matches would
  // hide the fact that the whole active set was evaluated.
  const matched = result.policyTrace.filter((entry) => entry.matched);
  const rest = result.policyTrace.filter((entry) => !entry.matched);

  return (
    <Panel interactive={false}>
      <PanelHeader
        title="Policy Trace"
        icon={ShieldAlert}
        description={`${matched.length} of ${result.policyTrace.length} active rules matched.`}
        action={
          <StatusChip tone={EFFECT_TONE[result.policyEffect]}>
            {EFFECT_LABELS[result.policyEffect]}
          </StatusChip>
        }
      />
      <ul className="divide-y divide-white/5">
        {[...matched, ...rest].map((entry) => (
          <li
            key={entry.policyId}
            className={cn(
              "flex flex-wrap items-center gap-3 px-6 py-3",
              !entry.matched && "opacity-50",
            )}
          >
            <span className="font-mono text-body-sm text-outline">{entry.policyId}</span>
            <span className="min-w-0 flex-1 truncate text-body-sm text-on-surface">
              {entry.policyName}
            </span>
            <span className="font-mono text-status-label text-outline">{entry.version}</span>
            {entry.matched && entry.effect ? (
              <StatusChip tone={EFFECT_TONE[entry.effect]}>
                {EFFECT_LABELS[entry.effect]}
              </StatusChip>
            ) : (
              <span className="font-mono text-status-label uppercase text-outline">
                {entry.inScope ? "no match" : "out of scope"}
              </span>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function ScenarioWorkspace({ agents }: { agents: Agent[] }) {
  const [scenario, setScenario] = useState<Scenario>({
    ...DEFAULT_SCENARIO,
    agentId: agents[0]?.id ?? "",
  });
  const [result, setResult] = useState<SimulateActionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function set<K extends keyof Scenario>(key: K, value: Scenario[K]) {
    setScenario((current) => ({ ...current, [key]: value }));
    // The previous verdict describes inputs that no longer exist on screen;
    // keeping it visible would invite reading it as the answer to the new ones.
    setResult(null);
    setError(null);
  }

  function run() {
    startTransition(async () => {
      setError(null);
      try {
        const amount = scenario.amountUsd.trim();
        const trust = scenario.trustScore.trim();
        const hour = scenario.hourUtc.trim();
        setResult(
          await runSimulation({
            agentId: scenario.agentId || null,
            action: scenario.action.trim() || "Proposed action",
            amountUsd: amount === "" ? null : Number(amount),
            riskScore: scenario.riskScore,
            trustScore: trust === "" ? null : Number(trust),
            hourUtc: hour === "" ? null : Number(hour),
          }),
        );
      } catch (err) {
        setResult(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  const selectedAgent = agents.find((agent) => agent.id === scenario.agentId);

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <div className="xl:col-span-4">
        <Panel className="h-full" interactive={false}>
          <PanelHeader
            title="Proposed Action"
            description="Nothing here is recorded — this is a what-if, not a decision."
          />
          <div className="flex flex-col gap-4 p-6">
            <Labelled label="Agent">
              <select
                className={FIELD_CLASS}
                value={scenario.agentId}
                onChange={(e) => set("agentId", e.target.value)}
              >
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </Labelled>

            <Labelled label="Action">
              <input
                className={FIELD_CLASS}
                value={scenario.action}
                maxLength={300}
                onChange={(e) => set("action", e.target.value)}
              />
            </Labelled>

            <Labelled label="Amount (USD)" hint="Leave blank for non-monetary actions.">
              <input
                className={FIELD_CLASS}
                inputMode="decimal"
                value={scenario.amountUsd}
                placeholder="none"
                onChange={(e) => set("amountUsd", e.target.value)}
              />
            </Labelled>

            <Labelled label={`Risk score — ${scenario.riskScore}`}>
              <input
                type="range"
                min={0}
                max={100}
                className="accent-primary"
                value={scenario.riskScore}
                onChange={(e) => set("riskScore", Number(e.target.value))}
              />
            </Labelled>

            <Labelled
              label="Trust override"
              hint={
                selectedAgent
                  ? `Blank uses ${selectedAgent.name}'s live score of ${selectedAgent.trustScore}.`
                  : "Blank uses the agent's live score."
              }
            >
              <input
                className={FIELD_CLASS}
                inputMode="numeric"
                value={scenario.trustScore}
                placeholder="live"
                onChange={(e) => set("trustScore", e.target.value)}
              />
            </Labelled>

            <Labelled label="Hour (UTC)" hint="Blank uses the current hour.">
              <input
                className={FIELD_CLASS}
                inputMode="numeric"
                value={scenario.hourUtc}
                placeholder="now"
                onChange={(e) => set("hourUtc", e.target.value)}
              />
            </Labelled>

            <GhostButton
              className="mt-1 flex items-center justify-center gap-2 py-2"
              onClick={run}
              disabled={pending}
            >
              <Play className="size-3.5" />
              {pending ? "Simulating…" : "Run simulation"}
            </GhostButton>
          </div>
        </Panel>
      </div>

      <div className="flex flex-col gap-4 xl:col-span-8">
        {error && (
          <p className="flex items-start gap-2 rounded border-l-2 border-error bg-error/5 px-4 py-3 text-body-sm text-error">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        )}

        {!result && !error && (
          <Panel className="flex h-full items-center justify-center p-12" interactive={false}>
            <p className="text-center text-body-md text-on-surface-variant">
              Set up an action and run it to see what ATLAS would decide — before anything
              executes.
            </p>
          </Panel>
        )}

        {result && (
          <>
            <Panel interactive={false}>
              <PanelHeader
                title={`${result.agentName} — verdict`}
                action={<OutcomeBadge outcome={result.recommendation} />}
              />
              <dl className="grid grid-cols-2 divide-white/5 md:grid-cols-4 md:divide-x">
                {[
                  { label: "Confidence", value: `${result.confidence}%` },
                  { label: "Trust", value: String(result.trustScore) },
                  { label: "Adverse", value: formatPercent(result.adverseProbability) },
                  { label: "Runtime", value: `${result.durationMs}ms` },
                ].map((item) => (
                  <div key={item.label} className="px-6 py-4">
                    <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                      {item.label}
                    </dt>
                    <dd className="mt-1 font-mono text-body-md text-on-surface">{item.value}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex flex-wrap gap-2 border-t border-white/5 px-6 py-3">
                {result.policyForced && (
                  <StatusChip tone="danger">Policy-forced</StatusChip>
                )}
                {!result.modelBacked && (
                  <StatusChip tone="neutral">No trained model — even split</StatusChip>
                )}
              </div>
              <ul className="flex flex-col gap-2 border-t border-white/5 px-6 py-4">
                {result.explanation.map((line) => (
                  <li key={line} className="text-body-sm text-on-surface-variant">
                    {line}
                  </li>
                ))}
              </ul>
            </Panel>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {result.outcomes.map((outcome) => (
                <OutcomeCard key={outcome.outcome} outcome={outcome} />
              ))}
            </div>

            <ExposureLedger result={result} />
            <PolicyTrace result={result} />
          </>
        )}
      </div>
    </div>
  );
}
