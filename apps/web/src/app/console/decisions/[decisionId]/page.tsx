import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  Check,
  Gavel,
  Lightbulb,
  ScrollText,
  TriangleAlert,
  X,
} from "lucide-react";

import { PolicyEvidence } from "@/components/decisions/policy-evidence";
import { ApiError as ApiErrorPanel } from "@/components/ui/api-error";
import { Meter } from "@/components/ui/charts";
import { DecisionSpine, SpineFacts, type SpineTone } from "@/components/ui/decision-spine";
import { trustColor, trustFill } from "@/components/ui/lifecycle-badge";
import { OutcomeBadge, riskColor } from "@/components/ui/outcome-badge";
import { Button, Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Pipeline } from "@/components/ui/pipeline";
import { StatusChip } from "@/components/ui/status-chip";
import { ApiError, fetchDecision, fetchLedger, tryFetch } from "@/lib/api";
import type { Decision, RiskVector } from "@/lib/types";
import { cn, formatTime, formatUsd } from "@/lib/utils";

export const dynamic = "force-dynamic";

const RISK_LABELS: { key: keyof RiskVector; label: string }[] = [
  { key: "financial", label: "Financial" },
  { key: "fraud", label: "Fraud" },
  { key: "operational", label: "Operational" },
  { key: "regulatory", label: "Regulatory" },
];

function riskBar(score: number): string {
  if (score >= 75) return "bg-error";
  if (score >= 50) return "bg-brand-amber";
  return "bg-on-surface-variant";
}

const OUTCOME_SPINE_TONE: Record<Decision["outcome"], SpineTone> = {
  approved: "success",
  escalated: "warning",
  blocked: "danger",
};

/** First and last 8 characters — enough to compare two hashes by eye. */
function abbreviate(hash: string): string {
  return hash.length > 20 ? `${hash.slice(0, 10)}…${hash.slice(-10)}` : hash;
}

export default async function DecisionInvestigationPage({
  params,
}: {
  params: Promise<{ decisionId: string }>;
}) {
  const { decisionId } = await params;

  let decision;
  try {
    decision = await fetchDecision(decisionId);
  } catch (err) {
    // A missing decision is a 404; anything else means the backend is unwell,
    // which deserves a different message than "not found".
    if (err instanceof ApiError && err.status === 404) notFound();
    return <ApiErrorPanel error={err instanceof Error ? err.message : String(err)} />;
  }

  // The pinned evidence for this decision, if it was committed through the
  // pipeline. Seeded history predates the ledger, so an empty result is a
  // normal state here, not a failure.
  const ledgerResult = await tryFetch(() =>
    fetchLedger({ subjectId: decision.id, limit: 1 }),
  );
  const entry = ledgerResult.ok ? (ledgerResult.data[0] ?? null) : null;

  const investigation = decision.investigation;
  const failedChecks = decision.policyChecks.filter((check) => !check.passed);
  const passedChecks = decision.policyChecks.length - failedChecks.length;
  const tone = OUTCOME_SPINE_TONE[decision.outcome];

  return (
    <>
      <Link
        href="/console/decisions"
        className="mb-4 inline-flex items-center gap-1.5 text-body-sm text-on-surface-variant transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-3.5" />
        All decisions
      </Link>

      {/* --- Identity band: what was decided, about what, and when --------- */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2.5">
            <span className="rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-mono text-on-surface-variant">
              {decision.id}
            </span>
            <OutcomeBadge outcome={decision.outcome} />
          </div>
          <h1 className="text-headline-lg text-on-surface">{decision.action}</h1>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-body-md text-on-surface-variant">
            <Link
              href={`/console/agents/${encodeURIComponent(decision.agentId)}`}
              className="text-on-surface transition-colors hover:text-primary"
            >
              {decision.agentName}
            </Link>
            <span className="text-outline" aria-hidden>
              ·
            </span>
            {formatTime(decision.decidedAt)}
            <span className="text-outline" aria-hidden>
              ·
            </span>
            {decision.latencyMs}ms
          </p>
        </div>

        <div className="flex flex-wrap items-start gap-x-6 gap-y-3">
          {decision.amountUsd !== null && (
            <div className="text-right">
              <p className="eyebrow">Impact</p>
              <p className="mt-1 font-mono text-hero-num text-on-surface">
                {formatUsd(decision.amountUsd)}
              </p>
            </div>
          )}

          {/* The review controls the console has always carried here. They are
              unchanged: the API has no human-override endpoint yet, so these
              stay presentational until one exists. */}
          <div className="flex flex-wrap gap-2">
            <Button variant="danger">
              <X className="size-3.5" /> Reject
            </Button>
            <Button variant="secondary">
              <Check className="size-3.5" /> Approve
            </Button>
            <Button variant="ghost">
              <Gavel className="size-3.5" /> Escalate review
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-3">
        {/* ================= the spine ================= */}
        <div className="xl:col-span-2">
          <Panel>
            <PanelHeader
              title="Decision spine"
              description="Every decision passes the same five stages, in this order. This is what each one concluded."
            />
            <PanelBody className="px-4 py-5 sm:px-5">
              <DecisionSpine
                stages={[
                  {
                    key: "request",
                    label: "Request",
                    verdict: "What the agent asked to do",
                    tone: "neutral",
                    children: (
                      <SpineFacts
                        facts={[
                          { label: "Agent", value: decision.agentName },
                          { label: "Action", value: decision.action },
                          {
                            label: "Impact",
                            value: formatUsd(decision.amountUsd),
                            mono: decision.amountUsd !== null,
                          },
                          {
                            label: "Context",
                            value:
                              investigation?.merchant ??
                              investigation?.requestedAtLocal ??
                              "No additional context recorded",
                          },
                        ]}
                      />
                    ),
                  },
                  {
                    key: "policy",
                    label: "Policy",
                    verdict: (
                      <span className={failedChecks.length > 0 ? "text-error" : undefined}>
                        {passedChecks}/{decision.policyChecks.length} rules passed
                      </span>
                    ),
                    tone: failedChecks.length > 0 ? "danger" : "success",
                    children: <PolicyEvidence checks={decision.policyChecks} />,
                  },
                  {
                    key: "trust",
                    label: "Trust",
                    verdict: (
                      <span className={trustColor(decision.trustScore)}>
                        {decision.trustScore} / 100 at decision time
                      </span>
                    ),
                    tone: decision.trustScore >= 75 ? "success" : "warning",
                    children: (
                      <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
                        <div className="min-w-[180px] flex-1">
                          <Meter
                            value={decision.trustScore}
                            color={trustFill(decision.trustScore)}
                            thickness="h-1.5"
                          />
                          <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-body-sm text-on-surface-variant">
                            {investigation ? (
                              <span>
                                Moved{" "}
                                <span className="font-mono text-on-surface">
                                  {investigation.trustBefore}
                                </span>{" "}
                                <span className="text-outline">→</span>{" "}
                                <span
                                  className={cn(
                                    "font-mono",
                                    trustColor(decision.trustScore),
                                  )}
                                >
                                  {decision.trustScore}
                                </span>{" "}
                                on this decision
                              </span>
                            ) : (
                              <span>No re-evaluation recorded against this decision.</span>
                            )}
                          </div>
                        </div>

                        <div className="min-w-[150px]">
                          <p className="eyebrow">Risk</p>
                          <p
                            className={cn(
                              "mt-1 font-mono text-metric-num",
                              riskColor(decision.riskScore),
                            )}
                          >
                            {decision.riskScore}
                            <span className="ml-1 text-label-mono-xs text-outline">/100</span>
                          </p>
                        </div>

                        {investigation && (
                          <div className="min-w-[150px]">
                            <p className="eyebrow">Model certainty</p>
                            <p className="mt-1 font-mono text-metric-num text-on-surface">
                              {investigation.confidence}%
                            </p>
                          </div>
                        )}
                      </div>
                    ),
                  },
                  {
                    key: "decision",
                    label: "Decision",
                    verdict: <OutcomeBadge outcome={decision.outcome} />,
                    tone,
                    children: (
                      <div className="space-y-3">
                        <p className="text-body-md text-on-surface-variant">
                          {investigation?.summary ?? decision.rationale}
                        </p>

                        {investigation && investigation.criticalFactors.length > 0 && (
                          <ul className="space-y-2">
                            {investigation.criticalFactors.map((factor) => (
                              <li
                                key={factor.key}
                                className="flex gap-2.5 rounded-md border border-outline-variant bg-surface-container-high px-3 py-2.5"
                              >
                                <TriangleAlert
                                  className={cn(
                                    "mt-0.5 size-3.5 shrink-0",
                                    factor.severity === "critical"
                                      ? "text-error"
                                      : "text-brand-amber",
                                  )}
                                  strokeWidth={1.75}
                                />
                                <div className="min-w-0">
                                  <p className="text-body-md text-on-surface">
                                    {factor.title}
                                  </p>
                                  <p className="mt-0.5 text-body-sm text-on-surface-variant">
                                    {factor.detail}
                                  </p>
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}

                        {investigation?.actionRequired && (
                          <p className="border-l-2 border-primary bg-primary/[0.05] px-3 py-2 text-body-sm text-on-surface">
                            <span className="eyebrow mr-1.5 text-primary">
                              Action required
                            </span>
                            {investigation.actionRequired}
                          </p>
                        )}
                      </div>
                    ),
                  },
                  {
                    key: "ledger",
                    label: "Ledger",
                    verdict: entry ? (
                      <StatusChip tone="success">Recorded · #{entry.seq}</StatusChip>
                    ) : (
                      <StatusChip tone="neutral">No entry</StatusChip>
                    ),
                    tone: entry ? "brand" : "neutral",
                    children: entry ? (
                      <SpineFacts
                        columns={2}
                        facts={[
                          {
                            label: "Entry hash",
                            value: (
                              <span title={entry.entryHash}>
                                {abbreviate(entry.entryHash)}
                              </span>
                            ),
                            mono: true,
                          },
                          {
                            label: "Previous hash",
                            value: (
                              <span title={entry.prevHash}>{abbreviate(entry.prevHash)}</span>
                            ),
                            mono: true,
                          },
                          {
                            label: "Recorded",
                            value: formatTime(entry.recordedAt),
                            mono: true,
                          },
                          {
                            label: "Verification",
                            value: (
                              <Link
                                href="/console/ledger"
                                className="inline-flex items-center gap-1 text-primary hover:underline"
                              >
                                <ScrollText className="size-3.5" /> Open the ledger
                              </Link>
                            ),
                          },
                        ]}
                      />
                    ) : (
                      <p className="text-body-sm text-outline">
                        This decision predates the governance ledger, so there is no pinned
                        evidence to verify against. Decisions committed through the pipeline
                        are hash-chained from the moment they are recorded.
                      </p>
                    ),
                  },
                ]}
              />
            </PanelBody>
          </Panel>
        </div>

        {/* ================= supporting evidence ================= */}
        <div className="flex flex-col gap-4 xl:sticky xl:top-[76px]">
          <Panel>
            <PanelHeader title="At a glance" />
            <dl className="divide-y divide-outline-variant">
              {[
                {
                  label: "Trust at decision",
                  value: decision.trustScore,
                  tone: trustColor(decision.trustScore),
                },
                {
                  label: "Risk",
                  value: decision.riskScore,
                  tone: riskColor(decision.riskScore),
                },
                {
                  label: "Latency",
                  value: `${decision.latencyMs}ms`,
                  tone: "text-on-surface",
                },
                {
                  label: "Amount",
                  value: formatUsd(decision.amountUsd),
                  tone: "text-on-surface",
                },
                {
                  label: "Policies failed",
                  value: `${failedChecks.length} of ${decision.policyChecks.length}`,
                  tone: failedChecks.length > 0 ? "text-error" : "text-on-surface",
                },
              ].map((row) => (
                <div
                  key={row.label}
                  className="flex items-center justify-between gap-3 px-4 py-2.5"
                >
                  <dt className="text-body-sm text-on-surface-variant">{row.label}</dt>
                  <dd className={cn("font-mono text-body-md", row.tone)}>{row.value}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          {investigation && (
            <Panel>
              <PanelHeader
                title="Risk vector"
                description="Where the risk in this action actually sat."
              />
              <PanelBody className="space-y-3">
                {RISK_LABELS.map(({ key, label }) => {
                  const score = investigation.riskVector[key];
                  return (
                    <div key={key}>
                      <div className="mb-1.5 flex items-baseline justify-between">
                        <span className="text-body-sm text-on-surface-variant">{label}</span>
                        <span className={cn("font-mono text-body-sm", riskColor(score))}>
                          {score}
                        </span>
                      </div>
                      <Meter value={score} color={riskBar(score)} />
                    </div>
                  );
                })}
              </PanelBody>
            </Panel>
          )}

          <Panel>
            <PanelHeader
              title="Pipeline trace"
              description="Where this action travelled before it was allowed to run."
            />
            <PanelBody>
              <Pipeline
                dense
                stages={
                  investigation?.trace ?? [
                    { key: "request", label: "Request", status: "done" },
                    { key: "policy", label: "Policy", status: "done" },
                    { key: "trust", label: "Trust", status: "done" },
                    { key: "simulation", label: "Simulation", status: "done" },
                    { key: "ledger", label: "Ledger", status: "done" },
                  ]
                }
              />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="Go deeper" />
            <div className="divide-y divide-outline-variant">
              {[
                {
                  href: `/console/explain?decision=${encodeURIComponent(decision.id)}`,
                  icon: Lightbulb,
                  label: "Why this outcome",
                  detail: "Drivers, rules in force, and what would have changed it",
                },
                {
                  href: `/console/agents/${encodeURIComponent(decision.agentId)}`,
                  icon: Activity,
                  label: "How this agent behaves",
                  detail: "Trust history, compliance, and recent decisions",
                },
                {
                  href: "/console/ledger",
                  icon: ScrollText,
                  label: "Prove it happened",
                  detail: "The hash chain this decision is pinned into",
                },
              ].map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-container-high"
                >
                  <link.icon className="size-3.5 shrink-0 text-outline" strokeWidth={1.75} />
                  <span className="min-w-0">
                    <span className="block text-body-md text-on-surface">{link.label}</span>
                    <span className="block truncate text-body-sm text-outline">
                      {link.detail}
                    </span>
                  </span>
                </Link>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
