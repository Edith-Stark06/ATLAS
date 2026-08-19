import {
  BadgeCheck,
  Bot,
  Brain,
  Gavel,
  GitBranch,
  Rss,
  Scale,
  Shield,
  type LucideIcon,
} from "lucide-react";

import { ApiError } from "@/components/ui/api-error";
import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { PageHeader } from "@/components/ui/page-header";
import { Pipeline } from "@/components/ui/pipeline";
import { Sparkline } from "@/components/ui/sparkline";
import { StatCard, type StatTone } from "@/components/ui/stat-card";
import { StatusPip } from "@/components/ui/status-pip";
import { TrustRadar } from "@/components/ui/trust-radar";
import { fetchDashboard, tryFetch } from "@/lib/api";
import type { ActivityItem } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

const METRIC_ICONS: Record<string, LucideIcon> = {
  bot: Bot,
  shield: Shield,
  verified: BadgeCheck,
  policy: Scale,
  brain: Brain,
  gavel: Gavel,
};

const ACTIVITY_TONE: Record<ActivityItem["tone"], string> = {
  info: "bg-secondary",
  success: "bg-tertiary",
  warning: "bg-brand-amber",
  danger: "bg-error",
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

      <div className="mb-stack-md grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {metrics.map((metric) => (
          <StatCard
            key={metric.key}
            label={metric.label}
            value={metric.value}
            icon={METRIC_ICONS[metric.icon] ?? Bot}
            tone={metric.tone as StatTone}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          <Panel>
            <PanelHeader
              title="Dynamic Trust Intelligence"
              description="Every autonomous financial agent carries a continuously evolving Trust Score."
              action={<GhostButton>View Details</GhostButton>}
            />
            <div className="flex flex-col items-center gap-6 p-6 lg:flex-row lg:items-stretch">
              <div className="flex flex-1 items-center justify-center">
                <TrustRadar score={compositeTrust.score} factors={compositeTrust.factors} />
              </div>

              <aside className="w-full shrink-0 self-center rounded-lg border border-white/5 bg-surface-container-high/80 p-4 lg:w-48">
                <span className="mb-2 block font-mono text-label-mono text-on-surface-variant">
                  Recent Decision Trust
                </span>
                <Sparkline values={compositeTrust.trend} className="mb-2 h-12 w-full" />
                <div className="flex items-end justify-between">
                  <span className="text-body-sm text-on-surface-variant">Forecast</span>
                  <span
                    className={cn(
                      "text-headline-sm",
                      compositeTrust.predicted === null ? "text-outline" : "text-tertiary",
                    )}
                    title={
                      compositeTrust.predicted === null
                        ? "Awaiting the Trust Engine (Phase 3)"
                        : undefined
                    }
                  >
                    {compositeTrust.predicted ?? "—"}
                  </span>
                </div>
              </aside>
            </div>
            <p className="border-t border-white/5 px-6 py-3 text-center font-mono text-status-label text-on-surface-variant">
              Trust Score is computed from: {TRUST_INPUTS.join(" · ")}
            </p>
          </Panel>

          <Panel>
            <PanelHeader
              title="Live Decision Pipeline"
              icon={GitBranch}
              action={
                <span className="rounded bg-surface-variant px-2 py-1 font-mono text-status-label text-on-surface-variant">
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
          <Panel className="flex h-full flex-col">
            <PanelHeader title="Activity Feed" icon={Rss} />
            <ul className="flex-1 divide-y divide-white/5">
              {activity.map((item) => (
                <li key={item.id} className="flex gap-3 px-6 py-3.5">
                  <span
                    className={cn("mt-1.5 h-8 w-0.5 shrink-0 rounded", ACTIVITY_TONE[item.tone])}
                  />
                  <div className="min-w-0">
                    <p className="text-body-sm text-on-surface">{item.message}</p>
                    <p className="mt-1 font-mono text-status-label text-outline">
                      {formatTime(item.at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
            <footer className="flex items-center gap-2 border-t border-white/5 px-6 py-3">
              <StatusPip tone="up" pulse />
              <span className="font-mono text-label-mono text-on-surface-variant">
                Live from ATLAS API
              </span>
            </footer>
          </Panel>
        </div>
      </div>
    </>
  );
}
