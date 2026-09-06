import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Medal, Scale, ScrollText } from "lucide-react";

import { DecisionCard } from "@/components/console/decision-card";
import { ApiError as ApiErrorPanel, EmptyState } from "@/components/ui/api-error";
import { ChartLegend, Donut, SERIES_COLORS, TrendLine } from "@/components/ui/charts";
import { DriftBadge } from "@/components/ui/drift-badge";
import { LifecycleBadge } from "@/components/ui/lifecycle-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelBody, PanelFooter, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip } from "@/components/ui/status-chip";
import { TrustDial, TrustFactors } from "@/components/ui/trust-gauge";
import {
  ApiError,
  fetchAgent,
  fetchAgentTrust,
  fetchDecisions,
  tryFetch,
} from "@/lib/api";
import { cn, formatTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** Enough recent decisions to show a pattern without becoming the ledger. */
const RECENT_LIMIT = 8;

export default async function AgentDetailPage({
  params,
}: {
  params: Promise<{ agentId: string }>;
}) {
  const { agentId } = await params;

  let agent;
  try {
    agent = await fetchAgent(agentId);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) notFound();
    return <ApiErrorPanel error={err instanceof Error ? err.message : String(err)} />;
  }

  // Trust history and the estate's decision list. Both are optional here: the
  // page is still worth rendering for an agent with no history yet.
  const [trustResult, decisionsResult] = await Promise.all([
    tryFetch(() => fetchAgentTrust(agent.id)),
    tryFetch(fetchDecisions),
  ]);

  const trust = trustResult.ok ? trustResult.data : null;
  const decisions = decisionsResult.ok
    ? decisionsResult.data.filter((decision) => decision.agentId === agent.id)
    : [];

  const approved = decisions.filter((d) => d.outcome === "approved").length;
  const escalated = decisions.filter((d) => d.outcome === "escalated").length;
  const blocked = decisions.filter((d) => d.outcome === "blocked").length;

  const checks = decisions.flatMap((decision) => decision.policyChecks);
  const passedChecks = checks.filter((check) => check.passed).length;
  const compliance = checks.length > 0 ? (passedChecks / checks.length) * 100 : null;

  const history = trust?.history.map((snapshot) => snapshot.score) ?? [];

  return (
    <>
      <Link
        href="/console/agents"
        className="mb-4 inline-flex items-center gap-1.5 text-body-sm text-on-surface-variant transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-3.5" />
        Agent registry
      </Link>

      <PageHeader
        eyebrow={agent.capability}
        title={agent.name}
        description={
          <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
            <span className="font-mono text-label-mono text-outline">{agent.id}</span>
            <span className="text-outline" aria-hidden>
              ·
            </span>
            Owned by {agent.owner}
            <span className="text-outline" aria-hidden>
              ·
            </span>
            Authority level {agent.authorityLevel}
          </span>
        }
        action={
          <>
            <LifecycleBadge state={agent.lifecycle} />
            {trust && <DriftBadge drift={trust.drift} />}
          </>
        }
      />

      <div className="mb-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard
          label="Trust score"
          value={String(agent.trustScore)}
          hint="/ 100"
          tone={agent.trustScore >= 75 ? "tertiary" : agent.trustScore >= 60 ? "warning" : "error"}
          delta={`${agent.trustDelta >= 0 ? "+" : ""}${agent.trustDelta.toFixed(1)}/24h`}
          deltaTone={agent.trustDelta > 0.5 ? "up" : agent.trustDelta < -0.5 ? "down" : "neutral"}
          featured
        />
        <StatCard
          label="Decisions today"
          value={agent.decisionsToday.toLocaleString("en-US")}
        />
        <StatCard
          label="Policy compliance"
          value={compliance === null ? "—" : `${compliance.toFixed(1)}%`}
          hint={checks.length > 0 ? `${checks.length} checks` : "no checks recorded"}
          tone={compliance !== null && compliance < 95 ? "warning" : "tertiary"}
        />
        <StatCard
          label="Forecast"
          value={trust?.forecast === null || trust === null ? "—" : String(trust.forecast)}
          hint={trust?.forecast == null ? "not enough history" : "next evaluation"}
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-3">
        <div className="flex flex-col gap-4 xl:col-span-2">
          {/* --- Trust, decomposed --- */}
          <Panel>
            <PanelHeader
              title="Trust"
              description={
                trust
                  ? `Scored by the ${trust.scoreSource === "ml" ? "trained model" : "heuristic"}, from ${trust.factors.length} weighted factors.`
                  : "Factors carried on the agent record."
              }
              action={
                trust?.mlAnomaly?.detected ? (
                  <StatusChip tone="warning">Anomaly detected</StatusChip>
                ) : undefined
              }
            />
            <PanelBody className="flex flex-wrap items-center gap-x-6 gap-y-4">
              <TrustDial score={agent.trustScore} label="Trust" />
              <TrustFactors
                factors={trust?.factors ?? agent.factors}
                className="min-w-[260px] flex-1"
              />
            </PanelBody>

            {history.length > 1 && (
              <div className="flex items-center gap-4 border-t border-outline-variant px-4 py-3">
                <div className="shrink-0">
                  <p className="eyebrow">Trust trend</p>
                  <p className="mt-0.5 text-body-sm text-outline">
                    {history.length} snapshots
                  </p>
                </div>
                <TrendLine
                  values={history}
                  gradientId={`agent-trend-${agent.id}`}
                  color={
                    trust && trust.drift.delta < 0
                      ? "var(--color-error)"
                      : "var(--color-tertiary)"
                  }
                  className="h-10 min-w-0 flex-1"
                />
                <div className="shrink-0 text-right">
                  <p className="eyebrow">Baseline</p>
                  <p className="mt-0.5 font-mono text-body-md text-on-surface">
                    {trust?.drift.baseline?.toFixed(1) ?? "—"}
                  </p>
                </div>
              </div>
            )}
          </Panel>

          {/* --- Why this score --- */}
          {trust && trust.explanation.length > 0 && (
            <Panel>
              <PanelHeader title="Why this score" />
              <ol className="divide-y divide-outline-variant">
                {trust.explanation.map((line, index) => (
                  <li key={line} className="flex gap-2.5 px-4 py-2.5">
                    <span className="mt-0.5 font-mono text-label-mono-xs text-outline">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-body-sm text-on-surface-variant">{line}</span>
                  </li>
                ))}
              </ol>
              {trust.anomalyPenalty > 0 && (
                <PanelFooter>
                  Base{" "}
                  <span className="font-mono text-on-surface">
                    {trust.baseScore.toFixed(1)}
                  </span>{" "}
                  less an anomaly penalty of{" "}
                  <span className="font-mono text-error">
                    {trust.anomalyPenalty.toFixed(1)}
                  </span>
                  .
                </PanelFooter>
              )}
            </Panel>
          )}

          {/* --- Recent decisions --- */}
          <Panel>
            <PanelHeader
              title="Recent decisions"
              description="What this agent has actually been doing."
              action={
                <Link
                  href="/console/decisions"
                  className="text-body-sm text-on-surface-variant transition-colors hover:text-primary"
                >
                  All decisions →
                </Link>
              }
            />
            {decisions.length > 0 ? (
              <div className="divide-y divide-outline-variant">
                {decisions.slice(0, RECENT_LIMIT).map((decision) => (
                  <DecisionCard key={decision.id} decision={decision} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No decisions on record"
                description="This agent has not yet routed an action through the pipeline, so its score rests on seeded factors rather than observed behaviour."
              />
            )}
          </Panel>
        </div>

        <div className="flex flex-col gap-4 xl:sticky xl:top-[76px]">
          {/* --- Outcome mix --- */}
          {decisions.length > 0 && (
            <Panel>
              <PanelHeader
                title="Outcome mix"
                description={`Across ${decisions.length} recorded decisions.`}
              />
              <PanelBody className="flex flex-wrap items-center gap-5">
                <Donut
                  slices={[
                    { label: "approved", value: approved, color: SERIES_COLORS.approved },
                    { label: "escalated", value: escalated, color: SERIES_COLORS.escalated },
                    { label: "blocked", value: blocked, color: SERIES_COLORS.blocked },
                  ]}
                  centerValue={decisions.length}
                  centerLabel="decisions"
                />
                <ChartLegend
                  className="min-w-[110px] flex-1 flex-col !items-start gap-2"
                  items={[
                    {
                      label: "approved",
                      value: String(approved),
                      color: SERIES_COLORS.approved,
                    },
                    {
                      label: "escalated",
                      value: String(escalated),
                      color: SERIES_COLORS.escalated,
                    },
                    { label: "blocked", value: String(blocked), color: SERIES_COLORS.blocked },
                  ]}
                />
              </PanelBody>
            </Panel>
          )}

          {/* --- Risk signals --- */}
          <Panel>
            <PanelHeader title="Risk signals" />
            <dl className="divide-y divide-outline-variant">
              {[
                {
                  label: "Drift vs. own baseline",
                  value: trust
                    ? trust.drift.baseline === null
                      ? "No history"
                      : `${trust.drift.delta > 0 ? "+" : ""}${trust.drift.delta.toFixed(1)} pts`
                    : "—",
                  tone:
                    trust && trust.drift.detected ? "text-error" : "text-on-surface",
                },
                {
                  label: "Model anomaly",
                  value: trust?.mlAnomaly
                    ? trust.mlAnomaly.detected
                      ? `Detected (${trust.mlAnomaly.score.toFixed(3)})`
                      : "None"
                    : "Not scored",
                  tone: trust?.mlAnomaly?.detected ? "text-error" : "text-on-surface",
                },
                {
                  label: "Blocked actions",
                  value: String(blocked),
                  tone: blocked > 0 ? "text-error" : "text-on-surface",
                },
                {
                  label: "Escalated actions",
                  value: String(escalated),
                  tone: escalated > 0 ? "text-brand-amber" : "text-on-surface",
                },
                {
                  label: "Last audited",
                  value: agent.lastAuditAt,
                  tone: "text-on-surface",
                },
              ].map((row) => (
                <div
                  key={row.label}
                  className="flex items-center justify-between gap-3 px-4 py-2.5"
                >
                  <dt className="text-body-sm text-on-surface-variant">{row.label}</dt>
                  <dd className={cn("font-mono text-body-sm", row.tone)}>{row.value}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          {/* --- Cross-links --- */}
          <Panel>
            <PanelHeader title="Compare and govern" />
            <div className="divide-y divide-outline-variant">
              {[
                {
                  href: `/console/benchmark?cohort=${encodeURIComponent(agent.capability)}&agent=${encodeURIComponent(agent.id)}`,
                  icon: Medal,
                  label: "Benchmark against its cohort",
                  detail: `Other agents doing ${agent.capability}`,
                },
                {
                  href: "/console/policies",
                  icon: Scale,
                  label: "Rules that govern it",
                  detail: "Policy versions currently in force",
                },
                {
                  href: `/console/ledger`,
                  icon: ScrollText,
                  label: "Its evidence trail",
                  detail: "Hash-chained records of what it did",
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

      {trust && trust.history.length > 0 && (
        <p className="mt-4 text-body-sm text-outline">
          Last evaluated {formatTime(trust.history[trust.history.length - 1].capturedAt)} ·{" "}
          {trust.history.length} snapshots on record ·{" "}
          <span className="capitalize">{trust.scoreSource === "ml" ? "model" : "heuristic"}</span>{" "}
          scored
        </p>
      )}
    </>
  );
}
