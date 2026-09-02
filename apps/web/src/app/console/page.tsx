import {
  BadgeCheck,
  Bot,
  Brain,
  Gavel,
  GitBranch,
  LineChart,
  Rss,
  Scale,
  Shield,
  type LucideIcon,
} from "lucide-react";

import { LiveActivityFeed } from "@/components/live/live-activity-feed";
import { ApiError } from "@/components/ui/api-error";
import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { PageHeader } from "@/components/ui/page-header";
import { Pipeline } from "@/components/ui/pipeline";
import { Sparkline } from "@/components/ui/sparkline";
import { StatCard, type StatTone } from "@/components/ui/stat-card";
import { StatusPip } from "@/components/ui/status-pip";
import { TrustGauge } from "@/components/ui/trust-gauge";
import { fetchDashboard, tryFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const METRIC_ICONS: Record<string, LucideIcon> = {
  bot: Bot,
  shield: Shield,
  verified: BadgeCheck,
  policy: Scale,
  brain: Brain,
  gavel: Gavel,
};

const TRUST_INPUTS = [
  "Historical Behaviour",
  "Policy Compliance",
  "Context Awareness",
  "Risk Exposure",
  "Operational Reliability",
  "Anomaly Detection",
];

export default async function ControlCenterPage() {
  const result = await tryFetch(fetchDashboard);

  if (!result.ok) {
    return (
      <>
        <PageHeader
          title="Trust Every Decision."
          highlight="Verify Every Action."
          description="ATLAS continuously computes trust, enforces policy, simulates outcomes, explains every decision, and governs autonomous financial AI before execution."
        />
        <ApiError error={result.error} />
      </>
    );
  }

  const { metrics, compositeTrust, livePipeline, activity } = result.data;

  return (
    <>
      <PageHeader
        title="Trust Every Decision."
        highlight="Verify Every Action."
        description="ATLAS continuously computes trust, enforces policy, simulates outcomes, explains every decision, and governs autonomous financial AI before execution."
      />

      <div className="mb-col-gap grid grid-cols-2 gap-col-gap md:grid-cols-3 xl:grid-cols-6">
        {metrics.map((metric, i) => (
          <StatCard
            key={metric.key}
            label={metric.label}
            value={metric.value}
            icon={METRIC_ICONS[metric.icon] ?? Bot}
            tone={metric.tone as StatTone}
            delay={i * 60}
            // The composite trust score is the product's headline number, so
            // it gets the ringed treatment rather than sitting flush with the
            // five supporting metrics.
            featured={metric.key === "trust"}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-col-gap xl:grid-cols-12">
        <div className="flex flex-col gap-col-gap xl:col-span-8">
          <Panel
            delay={120}
            className="relative min-h-[520px] overflow-hidden bg-surface-container-low/50"
          >
            {/* Ambient bloom behind the gauge. */}
            <div className="pointer-events-none absolute left-1/2 top-1/2 size-[400px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-glow/10 blur-[100px]" />

            <div className="relative z-20 flex items-start justify-between gap-6 p-8 pb-0">
              <div>
                <h2 className="mb-2 text-[28px] font-bold tracking-tight text-white">
                  Dynamic Trust Intelligence
                </h2>
                <p className="max-w-md text-body-md text-on-surface-variant">
                  Every autonomous financial agent carries a continuously evolving Trust
                  Score, evaluated across {TRUST_INPUTS.length} critical dimensions.
                </p>
              </div>
              <GhostButton className="border-cyan-glow/40 bg-cyan-glow/5 uppercase tracking-widest text-cyan-glow hover:bg-cyan-glow/15 hover:shadow-[0_0_15px_rgb(6_182_212_/_0.2)]">
                View Details
              </GhostButton>
            </div>

            <div className="relative z-10 flex flex-col items-center gap-8 p-8 lg:flex-row lg:justify-center">
              <TrustGauge score={compositeTrust.score} factors={compositeTrust.factors} />

              <aside className="glass-overlay w-full shrink-0 animate-fade-in-up rounded-xl p-5 [animation-delay:800ms] lg:w-64">
                <div className="mb-4 flex items-center justify-between border-b border-white/5 pb-2">
                  <span className="font-mono text-label-mono uppercase tracking-wider text-on-surface-variant">
                    Recent Decision Trust
                  </span>
                  <LineChart className="size-4 text-cyan-glow" />
                </div>
                <Sparkline
                  values={compositeTrust.trend}
                  gradientId="composite-trend"
                  className="mb-3 h-16 w-full"
                />
                <div className="flex items-end justify-between">
                  <span className="text-body-sm text-on-surface-variant">Forecast</span>
                  <span
                    className={cn(
                      "text-headline-md font-bold tracking-tight",
                      compositeTrust.predicted === null
                        ? "text-outline"
                        : "text-tertiary-green drop-shadow-[0_0_10px_rgb(78_222_163_/_0.4)]",
                    )}
                    title={
                      compositeTrust.predicted === null
                        ? "Not enough evaluation rounds to project yet"
                        : undefined
                    }
                  >
                    {compositeTrust.predicted ?? "—"}
                  </span>
                </div>
              </aside>
            </div>

            {/* The six inputs, spelled out so the score never reads as a black box. */}
            <div className="relative z-10 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 border-t border-white/5 px-6 py-4">
              {TRUST_INPUTS.map((input, i) => (
                <span key={input} className="flex items-center gap-4">
                  <span className="font-mono text-label-mono-xs uppercase text-on-surface-variant">
                    {input}
                  </span>
                  {i < TRUST_INPUTS.length - 1 && (
                    <span className="text-cyan-glow/50" aria-hidden>
                      •
                    </span>
                  )}
                </span>
              ))}
            </div>
          </Panel>

          <Panel delay={240}>
            <PanelHeader
              title="Live Decision Pipeline"
              icon={GitBranch}
              action={
                <span className="rounded border border-white/5 bg-surface-variant px-2 py-1 font-mono text-status-label text-on-surface-variant">
                  Txn: #{livePipeline.transactionId}
                </span>
              }
            />
            <div className="p-6">
              <Pipeline stages={livePipeline.stages} />
            </div>
          </Panel>
        </div>

        <div className="xl:col-span-4">
          <Panel delay={300} className="flex h-full flex-col">
            <PanelHeader
              title="Activity Feed"
              icon={Rss}
              action={
                <span className="flex items-center gap-1.5 rounded-xl bg-tertiary-green/10 px-2 py-1">
                  <StatusPip tone="up" pulse />
                  <span className="font-mono text-status-label uppercase tracking-wider text-tertiary-green">
                    Live
                  </span>
                </span>
              }
            />
            <LiveActivityFeed initialActivity={activity} />
            <footer className="flex items-center gap-2 border-t border-white/5 px-6 py-3">
              <span className="font-mono text-label-mono-xs uppercase tracking-wider text-outline">
                Streaming from ATLAS API
              </span>
            </footer>
          </Panel>
        </div>
      </div>
    </>
  );
}
