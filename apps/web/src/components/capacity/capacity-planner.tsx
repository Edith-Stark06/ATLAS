"use client";

import { useState, useTransition } from "react";
import { AlertTriangle, ArrowUpRight, Gauge, Users } from "lucide-react";

import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { planCapacity } from "@/lib/api-client";
import type { Cohort, CapacityAgentPlan, CapacityPlan } from "@/lib/types";
import { cn } from "@/lib/utils";

const FIELD_CLASS =
  "rounded border border-white/10 bg-surface-container-high px-2 py-1.5 font-mono text-body-sm text-on-surface focus:border-secondary focus:outline-none";

const ACTION_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  scale: "success",
  hold: "warning",
  fix_first: "danger",
  observe: "neutral",
};

const ACTION_LABEL: Record<string, string> = {
  scale: "Scale",
  hold: "Hold",
  fix_first: "Fix first",
  observe: "Observe",
};

function AgentRow({ entry }: { entry: CapacityAgentPlan }) {
  return (
    <li className="flex flex-wrap items-start gap-3 px-6 py-3">
      <span className="w-20 shrink-0">
        <StatusChip tone={ACTION_TONE[entry.action] ?? "neutral"}>
          {ACTION_LABEL[entry.action] ?? entry.action}
        </StatusChip>
      </span>

      <div className="min-w-0 flex-1 basis-52">
        <p className="text-body-sm text-on-surface">{entry.agentName}</p>
        <p className="mt-0.5 text-body-sm text-on-surface-variant">{entry.reason}</p>
      </div>

      <span className="shrink-0 text-right font-mono text-body-sm">
        <span className="text-on-surface-variant">{entry.currentDaily.toFixed(1)}</span>
        <span className="mx-1 text-outline">→</span>
        <span className={entry.changePct > 0 ? "text-tertiary" : "text-on-surface-variant"}>
          {entry.recommendedDaily.toFixed(1)}
        </span>
        <span className="ml-1.5 text-status-label text-outline">/day</span>
      </span>
    </li>
  );
}

export function CapacityPlanner({ cohorts }: { cohorts: Cohort[] }) {
  const [capability, setCapability] = useState(cohorts[0]?.capability ?? "");
  const [multiplier, setMultiplier] = useState(3);
  const [reviewerDays, setReviewerDays] = useState("2");
  const [reviewMinutes, setReviewMinutes] = useState("12");
  const [plan, setPlan] = useState<CapacityPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function run() {
    startTransition(async () => {
      setError(null);
      try {
        setPlan(
          await planCapacity({
            capability,
            multiplier,
            days: 30,
            reviewerDaysAvailable: Number(reviewerDays) || 0,
            reviewMinutes: Number(reviewMinutes) || 12,
          }),
        );
      } catch (err) {
        setPlan(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  const binding = plan?.constraints.find((c) => c.key === plan.bindingConstraint);

  return (
    <>
      <Panel className="mb-stack-md" interactive={false}>
        <PanelHeader
          title="Plan for growth"
          icon={Gauge}
          description="Projects what more volume would demand of governance — and which constraint runs out first."
        />

        <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-4">
          <label className="flex flex-col gap-1.5">
            <span className="font-mono text-status-label uppercase text-on-surface-variant">
              Job
            </span>
            <select
              className={FIELD_CLASS}
              value={capability}
              onChange={(e) => setCapability(e.target.value)}
            >
              {cohorts.map((cohort) => (
                <option key={cohort.capability} value={cohort.capability}>
                  {cohort.capability} ({cohort.agents})
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="font-mono text-status-label uppercase text-on-surface-variant">
              Reviewer-days available
            </span>
            <input
              className={FIELD_CLASS}
              inputMode="decimal"
              value={reviewerDays}
              onChange={(e) => setReviewerDays(e.target.value)}
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="font-mono text-status-label uppercase text-on-surface-variant">
              Minutes per review
            </span>
            <input
              className={FIELD_CLASS}
              inputMode="decimal"
              value={reviewMinutes}
              onChange={(e) => setReviewMinutes(e.target.value)}
            />
          </label>

          <GhostButton
            className="flex items-center justify-center gap-2 self-end py-2"
            onClick={run}
            disabled={pending || !capability}
          >
            <ArrowUpRight className="size-3.5" />
            {pending ? "Projecting…" : "Project"}
          </GhostButton>

          <label className="flex flex-col gap-1.5 md:col-span-4">
            <span className="font-mono text-status-label uppercase text-on-surface-variant">
              Target volume — {multiplier}× current
            </span>
            <input
              type="range"
              min={1}
              max={10}
              step={0.5}
              className="accent-primary"
              value={multiplier}
              onChange={(e) => setMultiplier(Number(e.target.value))}
            />
          </label>
        </div>

        {error && (
          <p className="mx-6 mb-6 flex items-start gap-2 rounded border-l-2 border-error bg-error/5 px-4 py-3 text-body-sm text-error">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            {error}
          </p>
        )}
      </Panel>

      {plan && (
        <>
          {/* --- the headline: what runs out first --- */}
          <Panel className="mb-stack-md" interactive={false}>
            <PanelHeader
              title="Verdict"
              icon={plan.feasible ? Gauge : AlertTriangle}
              action={
                <StatusChip tone={plan.feasible ? "success" : "danger"}>
                  {plan.feasible ? "Reachable" : "Not reachable"}
                </StatusChip>
              }
            />

            <div className="px-6 py-4">
              <p className="text-headline-sm text-on-surface">
                {plan.currentDaily.toFixed(0)} → {plan.targetDaily.toFixed(0)} decisions/day
              </p>

              {binding && (
                <p className="mt-3 text-body-sm text-on-surface-variant">
                  The limit is{" "}
                  <span className="text-on-surface">{binding.label.toLowerCase()}</span> —{" "}
                  {binding.detail}
                  {binding.shortfall > 0 && (
                    <>
                      {" "}
                      Short by{" "}
                      <span className="font-mono text-error">
                        {binding.shortfall.toFixed(1)} {binding.unit}
                      </span>
                      .
                    </>
                  )}
                </p>
              )}

              {plan.unallocatedDaily > 0 && (
                <p className="mt-2 text-body-sm text-brand-amber">
                  {plan.unallocatedDaily.toFixed(0)} decisions/day of the target could not be
                  given to any agent safely.
                </p>
              )}
            </div>

            <dl className="grid grid-cols-1 divide-white/5 border-t border-white/5 sm:grid-cols-3 sm:divide-x">
              {plan.constraints.map((constraint) => (
                <div key={constraint.key} className="px-6 py-4">
                  <dt className="flex items-center gap-1.5 font-mono text-status-label uppercase text-on-surface-variant">
                    {constraint.key === "human_review" && <Users className="size-3" />}
                    {constraint.label}
                    {constraint.key === plan.bindingConstraint && (
                      <span className="text-brand-amber">· binding</span>
                    )}
                  </dt>
                  <dd className="mt-1 font-mono text-body-md">
                    <span
                      className={cn(
                        constraint.satisfied ? "text-on-surface" : "text-error",
                      )}
                    >
                      {constraint.required.toFixed(1)}
                    </span>
                    <span className="text-outline"> / {constraint.available.toFixed(1)}</span>
                  </dd>
                  <dd className="mt-0.5 text-status-label text-outline">
                    {constraint.unit} · {(constraint.headroom * 100).toFixed(0)}% headroom
                  </dd>
                </div>
              ))}
            </dl>
          </Panel>

          {/* --- per-agent --- */}
          <Panel className="mb-stack-md" interactive={false}>
            <PanelHeader
              title="Who takes the extra work"
              description="Problems first. Quality gates growth — scaling a failing agent multiplies its failures rather than adding capacity."
            />
            <ul className="divide-y divide-white/5">
              {plan.agents.map((entry) => (
                <AgentRow key={entry.agentId} entry={entry} />
              ))}
            </ul>
          </Panel>

          {/* --- honesty --- */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Panel interactive={false}>
              <PanelHeader
                title="What this assumes"
                description="Every rate here was measured at today's volume."
              />
              <ul className="flex flex-col gap-2 px-6 py-4">
                {plan.assumptions.map((line) => (
                  <li key={line} className="text-body-sm text-on-surface-variant">
                    — {line}
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel interactive={false}>
              <PanelHeader
                title="What ATLAS cannot tell you"
                description="Stated, so this is not mistaken for a full plan."
              />
              <ul className="flex flex-col gap-2 px-6 py-4">
                {plan.outOfScope.map((line) => (
                  <li key={line} className="text-body-sm text-on-surface-variant">
                    — {line}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
