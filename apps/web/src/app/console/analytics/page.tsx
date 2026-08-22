import Link from "next/link";
import {
  Activity,
  BarChart3,
  Clock,
  Scale,
  ShieldAlert,
  TriangleAlert,
  UserCheck,
} from "lucide-react";

import { ApiError } from "@/components/ui/api-error";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchAnalytics, tryFetch } from "@/lib/api";
import type { AnalyticsBucket, AnalyticsDayPoint, GovernanceAnalytics } from "@/lib/types";
import { cn, formatUsd } from "@/lib/utils";

export const metadata = { title: "Governance Analytics — ATLAS" };
export const dynamic = "force-dynamic";

const WINDOWS = [7, 30, 90] as const;

const BAND_TONE: Record<string, string> = {
  trusted: "bg-tertiary",
  healthy: "bg-secondary",
  watch: "bg-brand-amber",
  restricted: "bg-error",
};

const OUTCOME_TONE: Record<string, string> = {
  approved: "bg-tertiary",
  escalated: "bg-brand-amber",
  blocked: "bg-error",
};

function StackedBar({
  buckets,
  tones,
}: {
  buckets: AnalyticsBucket[];
  tones: Record<string, string>;
}) {
  const total = buckets.reduce((sum, b) => sum + b.count, 0);

  return (
    <div className="px-6 py-4">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-container-highest">
        {total > 0 &&
          buckets.map((bucket) => (
            <span
              key={bucket.label}
              className={tones[bucket.label] ?? "bg-outline"}
              style={{ width: `${bucket.share * 100}%` }}
            />
          ))}
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {buckets.map((bucket) => (
          <div key={bucket.label}>
            <dt className="flex items-center gap-1.5 font-mono text-status-label uppercase text-on-surface-variant">
              <span
                className={cn("size-1.5 rounded-full", tones[bucket.label] ?? "bg-outline")}
              />
              {bucket.label}
            </dt>
            <dd className="mt-1 font-mono text-body-md text-on-surface">
              {bucket.count}
              <span className="ml-1.5 text-status-label text-outline">
                {(bucket.share * 100).toFixed(0)}%
              </span>
            </dd>
          </div>
        ))}
      </dl>

      {total === 0 && (
        <p className="mt-3 text-body-sm text-outline">
          Nothing recorded in this window.
        </p>
      )}
    </div>
  );
}

/** Stacked columns, one per day. Quiet days are rendered as empty columns
 * rather than skipped — a compressed axis makes a lull look like traffic. */
function DailyChart({ series }: { series: AnalyticsDayPoint[] }) {
  const peak = Math.max(...series.map((p) => p.total), 1);

  return (
    <div className="px-6 py-4">
      <div className="flex h-40 items-end gap-[2px]">
        {series.map((point) => {
          const height = (point.total / peak) * 100;
          return (
            <div
              key={point.day}
              className="group relative flex h-full flex-1 flex-col justify-end"
              title={`${point.day} — ${point.total} decision${point.total === 1 ? "" : "s"}`}
            >
              {point.total === 0 ? (
                <span className="h-px w-full bg-white/5" />
              ) : (
                <span
                  className="flex w-full flex-col-reverse overflow-hidden rounded-sm"
                  style={{ height: `${Math.max(height, 2)}%` }}
                >
                  {point.approved > 0 && (
                    <span
                      className="w-full bg-tertiary"
                      style={{ height: `${(point.approved / point.total) * 100}%` }}
                    />
                  )}
                  {point.escalated > 0 && (
                    <span
                      className="w-full bg-brand-amber"
                      style={{ height: `${(point.escalated / point.total) * 100}%` }}
                    />
                  )}
                  {point.blocked > 0 && (
                    <span
                      className="w-full bg-error"
                      style={{ height: `${(point.blocked / point.total) * 100}%` }}
                    />
                  )}
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-2 flex justify-between font-mono text-status-label text-outline">
        <span>{series[0]?.day}</span>
        <span>peak {peak}/day</span>
        <span>{series[series.length - 1]?.day}</span>
      </div>
    </div>
  );
}

function LatencyPanel({ analytics }: { analytics: GovernanceAnalytics }) {
  const { latency } = analytics;
  // A mean far below p99 means the average is hiding a tail. Worth calling
  // out rather than leaving the reader to compare two numbers.
  const tailHeavy = latency.samples > 0 && latency.p99 > latency.mean * 3;

  const rows = [
    { label: "p50", value: latency.p50, tone: "text-on-surface" },
    { label: "p95", value: latency.p95, tone: "text-on-surface" },
    { label: "p99", value: latency.p99, tone: tailHeavy ? "text-brand-amber" : "text-on-surface" },
    { label: "mean", value: latency.mean, tone: "text-on-surface-variant" },
    { label: "max", value: latency.max, tone: "text-on-surface-variant" },
  ];

  return (
    <Panel interactive={false}>
      <PanelHeader
        title="Governance overhead"
        icon={Clock}
        description="What the gate costs the actions passing through it."
        action={
          <StatusChip tone="neutral">{latency.samples.toLocaleString()} samples</StatusChip>
        }
      />
      <dl className="grid grid-cols-2 divide-white/5 sm:grid-cols-5 sm:divide-x">
        {rows.map((row) => (
          <div key={row.label} className="px-6 py-4 sm:px-4">
            <dt className="font-mono text-status-label uppercase text-on-surface-variant">
              {row.label}
            </dt>
            <dd className={cn("mt-1 font-mono text-body-md", row.tone)}>{row.value}ms</dd>
          </div>
        ))}
      </dl>
      <p className="border-t border-white/5 px-6 py-3 text-body-sm text-on-surface-variant">
        {tailHeavy ? (
          <>
            The tail is <span className="text-brand-amber">well above the mean</span> — the
            average understates what the slowest requests cost.
          </>
        ) : (
          <>Percentiles are nearest-rank, so each figure is a request that actually happened.</>
        )}
      </p>
    </Panel>
  );
}

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const params = await searchParams;
  const requested = Number(params.days);
  const days = WINDOWS.includes(requested as (typeof WINDOWS)[number]) ? requested : 30;

  const result = await tryFetch(() => fetchAnalytics(days));

  const header = (
    <PageHeader
      title="Governance"
      highlight="Analytics"
      description="Aggregate trends across agents, policies and decisions — computed from the records, never from a rollup that could drift."
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

  const analytics = result.data;
  const dead = analytics.hotspots.filter((h) => h.neverFired);

  return (
    <>
      {header}

      <div className="mb-stack-md flex flex-wrap gap-2">
        {WINDOWS.map((window) => (
          <Link
            key={window}
            href={`/console/analytics?days=${window}`}
            className={cn(
              "rounded border px-3 py-1.5 font-mono text-label-mono uppercase transition-colors",
              window === days
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-white/10 text-on-surface-variant hover:text-on-surface",
            )}
          >
            {window} days
          </Link>
        ))}
      </div>

      <div className="mb-stack-md grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Decisions"
          value={analytics.series.reduce((sum, p) => sum + p.total, 0).toLocaleString()}
          icon={Activity}
          tone="secondary"
        />
        <StatCard
          label="Held for review"
          value={`${analytics.review.rate.percent}%`}
          icon={UserCheck}
          tone="error"
        />
        <StatCard
          label="Exposure withheld"
          value={formatUsd(analytics.exposure.withheldUsd)}
          icon={Scale}
          tone="tertiary"
        />
        <StatCard label="p99 latency" value={`${analytics.latency.p99}ms`} icon={Clock} />
      </div>

      <div className="mb-stack-md grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel interactive={false}>
          <PanelHeader
            title="Decision volume"
            icon={BarChart3}
            description={`Daily mix over ${analytics.windowDays} days. Quiet days are shown, not skipped.`}
          />
          <DailyChart series={analytics.series} />
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel interactive={false}>
            <PanelHeader
              title="Estate trust"
              description={
                `${analytics.agents} agents. ` +
                (analytics.agentsWithoutDecisions === 0
                  ? "All have recorded decisions."
                  : `${analytics.agentsWithoutDecisions} ` +
                    `${analytics.agentsWithoutDecisions === 1 ? "has" : "have"} ` +
                    "no recorded decisions yet, so their score rests on seeded " +
                    "factors rather than on observed behaviour.")
              }
            />
            <StackedBar buckets={analytics.trust} tones={BAND_TONE} />
          </Panel>

          <Panel interactive={false}>
            <PanelHeader title="Outcome mix" description="Share of each verdict in the window." />
            <StackedBar buckets={analytics.outcomes} tones={OUTCOME_TONE} />
          </Panel>
        </div>
      </div>

      <div className="mb-stack-md grid grid-cols-1 gap-4 xl:grid-cols-2">
        <LatencyPanel analytics={analytics} />

        <Panel interactive={false}>
          <PanelHeader
            title="Review load"
            icon={UserCheck}
            description="What governance is asking humans to do."
          />
          <dl className="grid grid-cols-3 divide-white/5 sm:divide-x">
            <div className="px-6 py-4">
              <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                Escalated
              </dt>
              <dd className="mt-1 font-mono text-body-md text-on-surface">
                {analytics.review.escalated}
              </dd>
            </div>
            <div className="px-6 py-4">
              <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                Per day
              </dt>
              <dd className="mt-1 font-mono text-body-md text-on-surface">
                {analytics.review.perDay}
              </dd>
            </div>
            <div className="px-6 py-4">
              <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                Of total
              </dt>
              <dd className="mt-1 font-mono text-body-md text-on-surface">
                {analytics.review.rate.percent}%
                {/* The denominator, always. 8% of 12 is noise; 8% of 12,000
                    is a finding, and the reader cannot tell them apart without
                    the sample size. */}
                <span className="ml-1.5 text-status-label text-outline">
                  of {analytics.review.rate.total}
                </span>
              </dd>
            </div>
          </dl>
          <div className="border-t border-white/5 px-6 py-4">
            <p className="font-mono text-status-label uppercase text-on-surface-variant">
              Exposure
            </p>
            <p className="mt-1 text-body-sm text-on-surface-variant">
              <span className="font-mono text-on-surface">
                {formatUsd(analytics.exposure.movedUsd)}
              </span>{" "}
              moved,{" "}
              <span className="font-mono text-brand-amber">
                {formatUsd(analytics.exposure.withheldUsd)}
              </span>{" "}
              held back across {analytics.exposure.decisionsWithAmount} monetary
              {analytics.exposure.decisionsWithAmount === 1 ? " action" : " actions"}.
            </p>
          </div>
        </Panel>
      </div>

      <Panel interactive={false}>
        <PanelHeader
          title="Policy hot spots"
          icon={ShieldAlert}
          description="Which rules are doing the work — ranked by how often they restrict, not by how often they run."
          action={
            dead.length > 0 ? (
              <StatusChip tone="warning">{dead.length} never fired</StatusChip>
            ) : undefined
          }
        />

        {analytics.hotspots.length === 0 ? (
          <p className="px-6 py-4 text-body-sm text-outline">
            No policy checks recorded in this window.
          </p>
        ) : (
          <ul className="divide-y divide-white/5">
            {analytics.hotspots.map((hotspot) => (
              <li
                key={hotspot.policyId}
                className="flex flex-wrap items-center gap-3 px-6 py-3"
              >
                <span className="font-mono text-status-label text-outline">
                  {hotspot.policyId}
                </span>
                <span className="min-w-0 flex-1 basis-40 truncate text-body-sm text-on-surface">
                  {hotspot.policyName}
                </span>

                <div className="hidden h-1.5 w-24 overflow-hidden rounded-full bg-surface-container-highest sm:block">
                  <span
                    className="block h-full rounded-full bg-error"
                    style={{ width: `${hotspot.matchRate.percent}%` }}
                  />
                </div>

                <span className="w-28 text-right font-mono text-body-sm text-on-surface">
                  {hotspot.matchRate.percent}%
                  <span className="ml-1.5 text-status-label text-outline">
                    of {hotspot.evaluations}
                  </span>
                </span>

                {hotspot.neverFired && (
                  <StatusChip tone="warning">
                    <TriangleAlert className="mr-1 inline size-3" />
                    never fired
                  </StatusChip>
                )}
              </li>
            ))}
          </ul>
        )}

        {dead.length > 0 && (
          <p className="border-t border-white/5 px-6 py-3 text-body-sm text-on-surface-variant">
            A rule evaluated many times that has never once matched is either
            mis-scoped or redundant. Both are worth an author&apos;s attention — but
            neither is flagged until the rule has actually been tested enough times
            to mean something.
          </p>
        )}
      </Panel>
    </>
  );
}
