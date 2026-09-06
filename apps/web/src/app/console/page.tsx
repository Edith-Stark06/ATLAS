import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  Bot,
  Brain,
  Gavel,
  GitBranch,
  Radio,
  Scale,
  Shield,
  ShieldAlert,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";

import { AgentRow } from "@/components/console/agent-row";
import { DecisionCard } from "@/components/console/decision-card";
import { LiveActivityFeed } from "@/components/live/live-activity-feed";
import { ApiError, EmptyState } from "@/components/ui/api-error";
import {
  ChartLegend,
  Donut,
  SERIES_COLORS,
  StackedColumns,
  TrendLine,
} from "@/components/ui/charts";
import { trustColor } from "@/components/ui/lifecycle-badge";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { PageHeader } from "@/components/ui/page-header";
import { Pipeline } from "@/components/ui/pipeline";
import { StatCard, type StatTone } from "@/components/ui/stat-card";
import { StatusChip } from "@/components/ui/status-chip";
import { StatusPip } from "@/components/ui/status-pip";
import { TrustGauge } from "@/components/ui/trust-gauge";
import {
  fetchAgents,
  fetchAnalytics,
  fetchDashboard,
  fetchDecisions,
  fetchLedgerStats,
  tryFetch,
  verifyLedger,
} from "@/lib/api";
import type { Agent, Decision } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata = { title: "Mission Control — ATLAS" };
export const dynamic = "force-dynamic";

const METRIC_ICONS: Record<string, LucideIcon> = {
  bot: Bot,
  shield: Shield,
  verified: BadgeCheck,
  policy: Scale,
  brain: Brain,
  gavel: Gavel,
};

/** How many rows each roster shows before deferring to its own page. */
const LIVE_LIMIT = 10;
/** Split across the two kinds of attention, so neither crowds the other out. */
const ATTENTION_DECISIONS = 4;
const ATTENTION_AGENTS = 3;
const ROSTER_LIMIT = 6;

function SeeAll({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 text-body-sm text-on-surface-variant transition-colors hover:text-primary"
    >
      {children}
      <ArrowRight className="size-3" aria-hidden />
    </Link>
  );
}

/** A single governance-health reading: label, value, and a state dot. */
function HealthRow({
  label,
  value,
  tone,
  detail,
}: {
  label: string;
  value: React.ReactNode;
  tone: "up" | "warn" | "down" | "idle";
  detail?: string;
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <StatusPip tone={tone} />
      <span className="min-w-0 flex-1 truncate text-body-sm text-on-surface-variant">
        {label}
      </span>
      <span className="shrink-0 text-right">
        <span className="block text-body-md text-on-surface">{value}</span>
        {detail && <span className="block text-label-mono-xs text-outline">{detail}</span>}
      </span>
    </div>
  );
}

export default async function MissionControlPage() {
  // Everything on this page comes from the same five reads the console already
  // made; nothing here is computed from a number that was typed in.
  const [dashboardResult, analyticsResult, decisionsResult, agentsResult, ledgerResult, verifyResult] =
    await Promise.all([
      tryFetch(fetchDashboard),
      tryFetch(() => fetchAnalytics(30)),
      tryFetch(fetchDecisions),
      tryFetch(fetchAgents),
      tryFetch(fetchLedgerStats),
      tryFetch(verifyLedger),
    ]);

  const header = (
    <PageHeader
      eyebrow="Mission Control"
      title="Autonomous actions, governed in real time"
      description="Every consequential action an agent requests is evaluated against policy and trust before it runs, and recorded where it can be verified."
    />
  );

  if (!dashboardResult.ok) {
    return (
      <>
        {header}
        <ApiError error={dashboardResult.error} />
      </>
    );
  }

  const { metrics, compositeTrust, livePipeline, activity } = dashboardResult.data;
  const analytics = analyticsResult.ok ? analyticsResult.data : null;
  const decisions: Decision[] = decisionsResult.ok ? decisionsResult.data : [];
  const agents: Agent[] = agentsResult.ok ? agentsResult.data : [];
  const ledger = ledgerResult.ok ? ledgerResult.data : null;
  const verification = verifyResult.ok ? verifyResult.data : null;

  // Decisions that did not clear on their own — this is the queue a governance
  // operator actually works.
  const attention = decisions
    .filter((decision) => decision.outcome !== "approved")
    .slice(0, ATTENTION_DECISIONS);

  // Agents whose trust is falling fastest. Sorted by the movement, not the
  // score: a strong agent losing ground is the earlier signal.
  const declining = [...agents]
    .filter((agent) => agent.trustDelta < -0.5)
    .sort((a, b) => a.trustDelta - b.trustDelta)
    .slice(0, ATTENTION_AGENTS);

  const roster = [...agents]
    .sort((a, b) => b.decisionsToday - a.decisionsToday)
    .slice(0, ROSTER_LIMIT);

  const healthy = agents.filter(
    (agent) => agent.lifecycle === "healthy" || agent.lifecycle === "trusted",
  ).length;
  const needsAttention = agents.length - healthy;

  const outcomeSlices = analytics
    ? analytics.outcomes.map((bucket) => ({
        label: bucket.label,
        value: bucket.count,
        color:
          SERIES_COLORS[bucket.label as keyof typeof SERIES_COLORS] ?? SERIES_COLORS.neutral,
      }))
    : [];
  const outcomeTotal = outcomeSlices.reduce((sum, slice) => sum + slice.value, 0);

  return (
    <>
      {header}

      {/* --- Today's governance: the six figures the API already reports --- */}
      <section className="mb-4" aria-label="Today's governance">
        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
          {metrics.map((metric, index) => (
            <StatCard
              key={metric.key}
              label={metric.label}
              value={metric.value}
              icon={METRIC_ICONS[metric.icon] ?? Bot}
              tone={metric.tone as StatTone}
              delay={index * 30}
              // Composite trust is the product's headline number, so it carries
              // the one accented tile rather than sitting flush with the rest.
              featured={metric.key === "trust"}
            />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        {/* ================= main column ================= */}
        <div className="flex flex-col gap-4 xl:col-span-2">
          {/* --- Governance activity --- */}
          <Panel delay={40}>
            <PanelHeader
              title="Governance activity"
              description={
                analytics
                  ? `Decision volume over ${analytics.windowDays} days, split by verdict. Quiet days are shown, not skipped.`
                  : undefined
              }
              action={<SeeAll href="/console/analytics">Analytics</SeeAll>}
            />
            <PanelBody>
              {analytics && analytics.series.length > 0 ? (
                <>
                  <StackedColumns
                    points={analytics.series.map((point) => ({
                      label: point.day,
                      segments: [
                        {
                          key: "blocked",
                          value: point.blocked,
                          color: SERIES_COLORS.blocked,
                        },
                        {
                          key: "escalated",
                          value: point.escalated,
                          color: SERIES_COLORS.escalated,
                        },
                        {
                          key: "approved",
                          value: point.approved,
                          color: SERIES_COLORS.approved,
                        },
                      ],
                    }))}
                    startLabel={analytics.series[0]?.day}
                    endLabel={analytics.series[analytics.series.length - 1]?.day}
                  />
                  <ChartLegend
                    className="mt-3.5 border-t border-outline-variant pt-3"
                    items={analytics.outcomes.map((bucket) => ({
                      label: bucket.label,
                      value: bucket.count.toLocaleString("en-US"),
                      color:
                        SERIES_COLORS[bucket.label as keyof typeof SERIES_COLORS] ??
                        SERIES_COLORS.neutral,
                    }))}
                  />
                </>
              ) : (
                <EmptyState
                  title="No decision history yet"
                  description="Volume appears here once actions have been committed through the pipeline."
                />
              )}
            </PanelBody>
          </Panel>

          {/* --- Live governance --- */}
          <Panel delay={80}>
            <PanelHeader
              title="Live governance"
              description="The most recent actions to pass through the pipeline. Open one to see why it was decided that way."
              action={<SeeAll href="/console/decisions">All decisions</SeeAll>}
            />
            {decisions.length > 0 ? (
              <div className="divide-y divide-outline-variant">
                {decisions.slice(0, LIVE_LIMIT).map((decision) => (
                  <DecisionCard key={decision.id} decision={decision} />
                ))}
              </div>
            ) : (
              <EmptyState
                title="Nothing governed yet"
                description="Commit an action from Decisions and it will appear here."
              />
            )}
          </Panel>

          {/* Composite trust and the outcome mix read together: one says how
              far the estate is trusted, the other what that trust produced. */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          {/* --- Composite trust: preserved from the previous dashboard --- */}
          <Panel delay={120} className="lg:col-span-3">
            <PanelHeader
              title="Composite trust"
              description={`One score per agent estate, decomposed into the ${compositeTrust.factors.length} factors that produced it.`}
              action={<SeeAll href="/console/trust-engine">Trust &amp; risk</SeeAll>}
            />
            <PanelBody>
              <TrustGauge score={compositeTrust.score} factors={compositeTrust.factors} />
            </PanelBody>

            {compositeTrust.trend.length > 1 && (
              <div className="flex items-center gap-4 border-t border-outline-variant px-4 py-3">
                <div className="min-w-0 shrink-0">
                  <p className="eyebrow">Recent decision trust</p>
                  <p className="mt-0.5 text-body-sm text-outline">
                    {compositeTrust.trend.length} decisions
                  </p>
                </div>
                <TrendLine
                  values={compositeTrust.trend}
                  gradientId="composite-trend"
                  color="var(--color-primary)"
                  className="h-9 min-w-0 flex-1"
                />
                <div className="shrink-0 text-right">
                  <p className="eyebrow">Forecast</p>
                  <p
                    className={cn(
                      "mt-0.5 font-mono text-body-md",
                      compositeTrust.predicted === null
                        ? "text-outline"
                        : trustColor(compositeTrust.predicted),
                    )}
                    title={
                      compositeTrust.predicted === null
                        ? "Not enough evaluation rounds to project yet"
                        : undefined
                    }
                  >
                    {compositeTrust.predicted ?? "—"}
                  </p>
                </div>
              </div>
            )}
          </Panel>

          {analytics && outcomeTotal > 0 && (
            <Panel delay={140} className="lg:col-span-2">
              <PanelHeader
                title="Decision outcomes"
                description={`Over ${analytics.windowDays} days.`}
              />
              <PanelBody className="flex flex-wrap items-center gap-5">
                <Donut
                  slices={outcomeSlices}
                  centerValue={outcomeTotal.toLocaleString("en-US")}
                  centerLabel="decisions"
                />
                <ChartLegend
                  className="min-w-[120px] flex-1 flex-col !items-start gap-2"
                  items={analytics.outcomes.map((bucket) => ({
                    label: bucket.label,
                    value: `${(bucket.share * 100).toFixed(1)}%`,
                    color:
                      SERIES_COLORS[bucket.label as keyof typeof SERIES_COLORS] ??
                      SERIES_COLORS.neutral,
                  }))}
                />
              </PanelBody>
            </Panel>
          )}
          </div>

          {/* --- Live decision pipeline: preserved --- */}
          <Panel delay={160}>
            <PanelHeader
              title="Decision pipeline"
              icon={GitBranch}
              description="Where the most recent action currently sits in the governance sequence."
              action={
                <span className="rounded border border-outline-variant px-1.5 py-0.5 font-mono text-label-mono-xs text-outline">
                  {livePipeline.transactionId}
                </span>
              }
            />
            <PanelBody>
              <Pipeline stages={livePipeline.stages} />
            </PanelBody>
          </Panel>
        </div>

        {/* ================= side column ================= */}
        <div className="flex flex-col gap-4">
          {/* --- Requires attention --- */}
          <Panel delay={60}>
            <PanelHeader
              title="Requires attention"
              icon={TriangleAlert}
              description="What did not clear on its own."
            />
            {attention.length === 0 && declining.length === 0 ? (
              <EmptyState
                title="Nothing outstanding"
                description="No escalations, blocks, or falling trust scores right now."
              />
            ) : (
              <div className="divide-y divide-outline-variant">
                {attention.map((decision) => (
                  <Link
                    key={decision.id}
                    href={`/console/decisions/${encodeURIComponent(decision.id)}`}
                    className="group flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-container-high"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body-md text-on-surface">
                        {decision.agentName}
                      </p>
                      <p className="truncate text-body-sm text-on-surface-variant">
                        {decision.action}
                      </p>
                    </div>
                    <StatusChip
                      tone={decision.outcome === "blocked" ? "danger" : "warning"}
                    >
                      {decision.outcome}
                    </StatusChip>
                    <ArrowRight
                      className="size-3 shrink-0 text-outline opacity-0 transition-opacity group-hover:opacity-100"
                      aria-hidden
                    />
                  </Link>
                ))}

                {declining.map((agent) => (
                  <Link
                    key={agent.id}
                    href={`/console/agents/${encodeURIComponent(agent.id)}`}
                    className="group flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-container-high"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-body-md text-on-surface">{agent.name}</p>
                      <p className="truncate text-body-sm text-on-surface-variant">
                        Trust declining · {agent.trustDelta.toFixed(1)} pts in 24h
                      </p>
                    </div>
                    <StatusChip tone={agent.trustScore < 60 ? "danger" : "warning"}>
                      {agent.trustScore < 60 ? "High risk" : "Watch"}
                    </StatusChip>
                    <ArrowRight
                      className="size-3 shrink-0 text-outline opacity-0 transition-opacity group-hover:opacity-100"
                      aria-hidden
                    />
                  </Link>
                ))}
              </div>
            )}
          </Panel>

          {/* --- Governance health --- */}
          <Panel delay={100}>
            <PanelHeader title="Governance health" icon={ShieldAlert} />
            <div className="divide-y divide-outline-variant">
              <HealthRow
                label="Policy compliance"
                value={metrics.find((m) => m.key === "compliance")?.value ?? "—"}
                tone="up"
              />
              <HealthRow
                label="Ledger integrity"
                value={
                  verification ? (verification.valid ? "Verified" : "Broken") : "Unknown"
                }
                tone={verification ? (verification.valid ? "up" : "down") : "idle"}
                detail={
                  ledger?.entries
                    ? `${ledger.entries.toLocaleString("en-US")} entries`
                    : "no entries yet"
                }
              />
              <HealthRow
                label="Agent health"
                value={`${healthy} healthy`}
                tone={needsAttention > 0 ? "warn" : "up"}
                detail={needsAttention > 0 ? `${needsAttention} need attention` : undefined}
              />
              <HealthRow
                label="Estate trust"
                value={compositeTrust.score}
                tone={
                  compositeTrust.score >= 75 ? "up" : compositeTrust.score >= 60 ? "warn" : "down"
                }
              />
              <HealthRow
                label="Human review rate"
                value={metrics.find((m) => m.key === "review")?.value ?? "—"}
                tone="warn"
                detail={analytics ? `${analytics.review.perDay}/day` : undefined}
              />
            </div>
          </Panel>

          {/* --- Active agents --- */}
          <Panel delay={180}>
            <PanelHeader
              title="Active agents"
              description="Busiest first, by decisions today."
              action={<SeeAll href="/console/agents">Registry</SeeAll>}
            />
            {roster.length > 0 ? (
              <div className="divide-y divide-outline-variant">
                {roster.map((agent) => (
                  <AgentRow key={agent.id} agent={agent} compact />
                ))}
              </div>
            ) : (
              <EmptyState title="No agents registered" />
            )}
          </Panel>

          {/* --- Activity feed: preserved, still streaming --- */}
          <Panel delay={220} className="flex flex-col">
            <PanelHeader
              title="Activity"
              icon={Radio}
              action={
                <span className="inline-flex items-center gap-1.5 text-status-label uppercase text-tertiary">
                  <StatusPip tone="up" pulse />
                  Live
                </span>
              }
            />
            <LiveActivityFeed
              initialActivity={activity}
              className="max-h-[340px] overflow-y-auto"
            />
          </Panel>
        </div>
      </div>
    </>
  );
}
