import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  GitBranch,
  Lightbulb,
  Scale,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import { ApiError } from "@/components/ui/api-error";
import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchDecisions, fetchExplanation, tryFetch } from "@/lib/api";
import type { Counterfactual, ExplanationDriver, RuleEffect } from "@/lib/types";
import { cn, formatUsd } from "@/lib/utils";

export const metadata = { title: "Explain AI — ATLAS" };
export const dynamic = "force-dynamic";

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

function formatValue(field: string, value: number | null): string {
  if (value === null) return "—";
  if (field === "amount_usd") return formatUsd(value);
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

/** A signed contribution bar — negative left, positive right, from a shared
 * centre so the two directions are visually comparable. */
function DriverBar({ driver, scale }: { driver: ExplanationDriver; scale: number }) {
  const magnitude = Math.min(100, (Math.abs(driver.contribution) / scale) * 50);
  const positive = driver.contribution >= 0;

  return (
    <div className="flex items-center gap-3 px-6 py-3">
      <span className="w-44 shrink-0 truncate text-body-sm text-on-surface">{driver.label}</span>

      <div className="relative h-1.5 min-w-0 flex-1 rounded-full bg-surface-container-highest">
        <span className="absolute left-1/2 top-1/2 h-3 w-px -translate-y-1/2 bg-outline/40" />
        <span
          className={cn(
            "absolute top-0 h-1.5 rounded-full",
            positive ? "bg-tertiary" : "bg-error",
          )}
          style={
            positive
              ? { left: "50%", width: `${magnitude}%` }
              : { right: "50%", width: `${magnitude}%` }
          }
        />
      </div>

      <span
        className={cn(
          "w-16 shrink-0 text-right font-mono text-body-sm",
          positive ? "text-tertiary" : "text-error",
        )}
      >
        {driver.contribution > 0 ? "+" : ""}
        {driver.contribution.toFixed(3)}
      </span>
      <span className="w-10 shrink-0 text-right font-mono text-status-label text-outline">
        {driver.value ?? "—"}
      </span>
    </div>
  );
}

function CounterfactualCard({ counterfactual }: { counterfactual: Counterfactual }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-white/8 bg-surface-container-high/40 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-body-md text-on-surface">{counterfactual.label}</span>
        <StatusChip tone={counterfactual.exact ? "info" : "neutral"}>
          {counterfactual.exact ? "Exact" : "Estimated"}
        </StatusChip>
      </div>

      <div className="flex flex-wrap items-center gap-2 font-mono text-body-md">
        <span className="text-error">
          {formatValue(counterfactual.field, counterfactual.current)}
        </span>
        <ArrowRight className="size-3.5 text-outline" />
        <span className="text-tertiary">
          {counterfactual.direction === "at most" ? "≤ " : "≥ "}
          {formatValue(counterfactual.field, counterfactual.threshold)}
        </span>
        {/* The new outcome, not assumed to be approval — clearing a block can
            still leave a review requirement behind. */}
        <span className="ml-auto">
          <OutcomeBadge outcome={counterfactual.changesTo} />
        </span>
      </div>

      <p className="text-body-sm text-on-surface-variant">{counterfactual.detail}</p>
    </div>
  );
}

export default async function ExplainPage({
  searchParams,
}: {
  searchParams: Promise<{ decision?: string }>;
}) {
  const params = await searchParams;
  const decisionsResult = await tryFetch(fetchDecisions);

  const header = (
    <PageHeader
      title="Explain"
      highlight="AI"
      description="Why a decision came out the way it did — reconstructed from the evidence pinned at the time, not from today's rules."
    />
  );

  if (!decisionsResult.ok) {
    return (
      <>
        {header}
        <ApiError error={decisionsResult.error} />
      </>
    );
  }

  const decisions = decisionsResult.data;
  if (decisions.length === 0) {
    return (
      <>
        {header}
        <ApiError error="No decisions recorded yet — commit one from Decision Intelligence." />
      </>
    );
  }

  // Default to the newest decision so the page is useful without a query.
  const selectedId = params.decision ?? decisions[0].id;
  const explanationResult = await tryFetch(() => fetchExplanation(selectedId));

  return (
    <>
      {header}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="xl:col-span-4">
          <Panel className="h-full" interactive={false}>
            <PanelHeader
              title="Decisions"
              description="Pick one to see the reasoning behind it."
            />
            <ul className="max-h-[32rem] divide-y divide-white/5 overflow-y-auto">
              {decisions.map((decision) => (
                <li key={decision.id}>
                  <Link
                    href={`/console/explain?decision=${encodeURIComponent(decision.id)}`}
                    className={cn(
                      "flex flex-wrap items-center gap-2 px-6 py-3 transition-colors hover:bg-white/[0.02]",
                      decision.id === selectedId && "bg-primary/5",
                    )}
                  >
                    <span className="font-mono text-status-label text-outline">{decision.id}</span>
                    <span className="min-w-0 flex-1 basis-40 truncate text-body-sm text-on-surface">
                      {decision.action}
                    </span>
                    <OutcomeBadge outcome={decision.outcome} />
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 xl:col-span-8">
          {!explanationResult.ok ? (
            <ApiError error={explanationResult.error} />
          ) : (
            (() => {
              const explanation = explanationResult.data;
              const scale = Math.max(
                ...explanation.drivers.map((d) => Math.abs(d.contribution)),
                0.0001,
              );

              return (
                <>
                  <Panel interactive={false}>
                    <PanelHeader
                      title={explanation.action}
                      icon={Lightbulb}
                      action={<OutcomeBadge outcome={explanation.outcome} />}
                    />
                    <div className="px-6 py-4">
                      <p className="text-headline-sm text-on-surface">{explanation.headline}</p>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <StatusChip tone={explanation.decidedBy === "policy" ? "danger" : "info"}>
                          Decided by {explanation.decidedBy}
                        </StatusChip>
                        {explanation.fromPinnedEvidence ? (
                          <StatusChip tone="success">
                            Ledger #{explanation.ledgerSeq}
                          </StatusChip>
                        ) : (
                          <StatusChip tone="warning">No audit record</StatusChip>
                        )}
                      </div>

                      <ul className="mt-4 flex flex-col gap-2">
                        {explanation.narrative.map((line) => (
                          <li key={line} className="text-body-sm text-on-surface-variant">
                            {line}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </Panel>

                  <Panel interactive={false}>
                    <PanelHeader
                      title="What would have changed it"
                      icon={GitBranch}
                      description={
                        explanation.counterfactuals.length === 0
                          ? explanation.outcome === "approved"
                            ? "Nothing to change — this action was approved."
                            : "No single input change would have altered this verdict."
                          : "Each has been replayed against the full rule set, so each on its own really does change the outcome — to the verdict shown, which is not always approval."
                      }
                    />
                    {explanation.counterfactuals.length > 0 && (
                      <div className="grid grid-cols-1 gap-3 p-6 md:grid-cols-2">
                        {explanation.counterfactuals.map((counterfactual, i) => (
                          <CounterfactualCard
                            key={`${counterfactual.field}-${i}`}
                            counterfactual={counterfactual}
                          />
                        ))}
                      </div>
                    )}
                  </Panel>

                  {explanation.drivers.length > 0 && (
                    <Panel interactive={false}>
                      <PanelHeader
                        title="Trust drivers"
                        icon={Sparkles}
                        description="SHAP attribution over the trained trust model."
                        action={
                          explanation.driversAreCurrent ? (
                            <StatusChip tone="neutral">Current, not historical</StatusChip>
                          ) : undefined
                        }
                      />
                      <div className="divide-y divide-white/5">
                        {explanation.drivers.map((driver) => (
                          <DriverBar key={driver.key} driver={driver} scale={scale} />
                        ))}
                      </div>
                      <p className="border-t border-white/5 px-6 py-3 text-body-sm text-on-surface-variant">
                        Per-factor attribution is not snapshotted, so these describe the agent&apos;s
                        trust <span className="text-on-surface">today</span> — not at the moment of
                        this decision.
                      </p>
                    </Panel>
                  )}

                  <Panel interactive={false}>
                    <PanelHeader
                      title="Rules in force"
                      icon={ShieldAlert}
                      description="The versions evaluated at decision time, taken from the pinned record."
                    />
                    <ul className="divide-y divide-white/5">
                      {explanation.rules.map((rule) => (
                        <li
                          key={rule.policyId}
                          className={cn(
                            "flex flex-wrap items-center gap-3 px-6 py-3",
                            !rule.matched && "opacity-50",
                          )}
                        >
                          <span className="font-mono text-body-sm text-outline">
                            {rule.policyId}
                          </span>
                          <span className="min-w-0 flex-1 basis-40 truncate text-body-sm text-on-surface">
                            {rule.policyName}
                          </span>
                          <span className="font-mono text-status-label text-outline">
                            {rule.version}
                          </span>
                          {rule.matched && rule.effect ? (
                            <StatusChip tone={EFFECT_TONE[rule.effect]}>
                              {EFFECT_LABELS[rule.effect]}
                            </StatusChip>
                          ) : (
                            <span className="flex items-center gap-1.5 font-mono text-status-label uppercase text-outline">
                              {rule.inScope ? (
                                <>
                                  <BadgeCheck className="size-3" /> no match
                                </>
                              ) : (
                                <>
                                  <Scale className="size-3" /> out of scope
                                </>
                              )}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </Panel>
                </>
              );
            })()
          )}
        </div>
      </div>
    </>
  );
}
