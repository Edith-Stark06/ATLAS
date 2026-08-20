import { Activity, AlertTriangle, BrainCircuit, RefreshCw, ShieldCheck, Users } from "lucide-react";

import { runRecompute } from "@/app/(console)/trust-engine/actions";
import { ApiError } from "@/components/ui/api-error";
import { DriftBadge } from "@/components/ui/drift-badge";
import { LifecycleBadge, trustColor } from "@/components/ui/lifecycle-badge";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Sparkline } from "@/components/ui/sparkline";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchModelInfo, fetchTrustOverview, tryFetch } from "@/lib/api";
import type { TrustEvaluation } from "@/lib/types";
import { cn, formatTime } from "@/lib/utils";

interface TrustModelMetrics {
  trust_model: { baseline_auc: number; learned_auc: number; auc_improvement_pct: number };
  anomaly_detection: {
    baseline: { precision: number; recall: number; f1: number };
    learned: { precision: number; recall: number; f1: number };
  };
  simulation_model: {
    baseline_accuracy: number;
    learned_accuracy: number;
    baseline_log_loss: number;
    learned_log_loss: number;
  };
  dataset: { n_agents: number; n_steps: number };
}

export const metadata = { title: "Trust Engine — ATLAS" };
export const dynamic = "force-dynamic";

const BAND_TONE: Record<string, string> = {
  trusted: "bg-tertiary",
  healthy: "bg-primary",
  watch: "bg-brand-amber",
  restricted: "bg-error",
};

function ScoreBreakdown({ evaluation }: { evaluation: TrustEvaluation }) {
  const { baseScore, anomalyPenalty, score, scoreSource, mlAttribution } = evaluation;

  if (scoreSource === "ml" && mlAttribution) {
    const top = Object.entries(mlAttribution)
      .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
      .slice(0, 2);
    return (
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 font-mono text-status-label">
        <span className={cn("text-body-sm", trustColor(score))}>{score}</span>
        <span className="text-outline">·</span>
        {top.map(([key, value]) => (
          <span key={key} className={value >= 0 ? "text-tertiary" : "text-error"}>
            {key} {value >= 0 ? "+" : ""}
            {value.toFixed(1)}
          </span>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 font-mono text-status-label">
      <span className="text-on-surface-variant">{baseScore.toFixed(1)}</span>
      <span className="text-outline">base</span>
      {anomalyPenalty > 0 && (
        <>
          <span className="text-error">−{anomalyPenalty.toFixed(1)}</span>
          <span className="text-outline">penalty</span>
        </>
      )}
      <span className="text-outline">=</span>
      <span className={cn("text-body-sm", trustColor(score))}>{score}</span>
    </div>
  );
}

function AgentTrustRow({ evaluation }: { evaluation: TrustEvaluation }) {
  const history = evaluation.history.map((h) => h.score);
  const falling = evaluation.drift.delta < 0;

  return (
    <li className="flex flex-wrap items-center gap-4 px-6 py-4">
      <div className="min-w-[200px] flex-1">
        <p className="text-body-md text-on-surface">{evaluation.agentName}</p>
        <ScoreBreakdown evaluation={evaluation} />
      </div>

      <div className="w-28 shrink-0">
        {history.length > 1 ? (
          <Sparkline
            values={history}
            stroke={falling ? "var(--color-error)" : "var(--color-tertiary)"}
            className="h-8 w-full"
          />
        ) : (
          <span className="font-mono text-status-label text-outline">no history</span>
        )}
      </div>

      <div className="w-24 shrink-0 text-right">
        <span className="font-mono text-status-label text-outline">forecast</span>
        <p
          className={cn(
            "font-mono text-body-sm",
            evaluation.forecast === null ? "text-outline" : trustColor(evaluation.forecast),
          )}
          title={
            evaluation.forecast === null ? "Not enough history to project" : undefined
          }
        >
          {evaluation.forecast ?? "—"}
        </p>
      </div>

      <DriftBadge drift={evaluation.drift} />
      {evaluation.mlAnomaly?.detected && (
        <StatusChip tone="warning" className="gap-1">
          <BrainCircuit className="size-3" />
          ML anomaly
        </StatusChip>
      )}
      <LifecycleBadge state={evaluation.lifecycle} />
    </li>
  );
}

export default async function TrustEnginePage() {
  const [result, modelInfoResult] = await Promise.all([
    tryFetch(fetchTrustOverview),
    tryFetch(fetchModelInfo),
  ]);
  const modelInfo = modelInfoResult.ok ? modelInfoResult.data : null;
  const metrics = modelInfo?.metrics as TrustModelMetrics | null | undefined;

  if (!result.ok) {
    return (
      <>
        <PageHeader
          title="Trust"
          highlight="Engine"
          description="Continuous evaluation of every agent's trust score from behavioural, policy, and risk signals."
        />
        <ApiError error={result.error} />
      </>
    );
  }

  const overview = result.data;
  const worst = overview.watchlist[0];
  const totalBanded = overview.bands.reduce((sum, b) => sum + b.count, 0) || 1;

  return (
    <>
      <PageHeader
        title="Trust"
        highlight="Engine"
        description="Every score below is computed from stored factors and recorded decisions — never a stored constant. Recompute to evaluate the estate and capture a new snapshot."
        action={
          <form action={runRecompute}>
            <button
              type="submit"
              className="flex shrink-0 items-center gap-2 rounded border border-primary/30 bg-primary/5 px-3 py-1.5 font-mono text-label-mono text-primary transition-colors hover:bg-primary/10"
            >
              <RefreshCw className="size-3.5" />
              Recompute
            </button>
          </form>
        }
      />

      <div className="mb-stack-md grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Estate Trust"
          value={String(overview.averageScore)}
          icon={ShieldCheck}
          tone="tertiary"
        />
        <StatCard
          label="Agents Evaluated"
          value={String(overview.agentsEvaluated)}
          icon={Users}
          tone="secondary"
        />
        <StatCard
          label="Drifting"
          value={String(overview.drifting)}
          icon={AlertTriangle}
          tone={overview.drifting > 0 ? "error" : "tertiary"}
        />
        <StatCard
          label="Lowest Trust"
          value={worst ? String(Math.min(...overview.watchlist.map((w) => w.score))) : "—"}
          icon={Activity}
          tone="primary"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="xl:col-span-8">
          <Panel>
            <PanelHeader
              title="Agent Trust"
              description={
                overview.watchlist.length < overview.agentsEvaluated
                  ? `Worst drift first — showing ${overview.watchlist.length} of ${overview.agentsEvaluated} agents.`
                  : "Score, own-history trend, projection, and drift against each agent's baseline. Worst drift first."
              }
            />
            <ul className="divide-y divide-white/5">
              {overview.watchlist.map((evaluation) => (
                <AgentTrustRow key={evaluation.agentId} evaluation={evaluation} />
              ))}
            </ul>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <Panel>
            <PanelHeader title="Trust Distribution" description="Agents by score band." />
            <div className="flex flex-col gap-4 p-6">
              {overview.bands.map((band) => (
                <div key={band.band}>
                  <div className="mb-1.5 flex items-baseline justify-between">
                    <span className="text-body-sm text-on-surface-variant">{band.label}</span>
                    <span className="font-mono text-body-sm text-on-surface">{band.count}</span>
                  </div>
                  <div className="h-1 w-full overflow-hidden rounded-full bg-surface-container-high">
                    <div
                      className={cn("h-full rounded-full", BAND_TONE[band.band] ?? "bg-outline")}
                      style={{ width: `${(band.count / totalBanded) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {worst && (
            <Panel>
              <PanelHeader
                title="Why this score?"
                description={worst.agentName}
                icon={AlertTriangle}
              />
              <ol className="flex flex-col gap-3 p-6">
                {worst.explanation.map((line, i) => (
                  <li key={i} className="flex gap-3 text-body-sm text-on-surface-variant">
                    <span className="mt-0.5 font-mono text-status-label text-outline">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    {line}
                  </li>
                ))}
              </ol>
              {worst.history.length > 0 && (
                <p className="border-t border-white/5 px-6 py-3 font-mono text-status-label text-outline">
                  Last evaluated {formatTime(worst.history[worst.history.length - 1].capturedAt)}
                  {" · "}
                  {worst.history.length} snapshots
                </p>
              )}
            </Panel>
          )}

          <Panel>
            <PanelHeader
              title="Model vs. Heuristic"
              icon={BrainCircuit}
              description={
                metrics
                  ? `Trained on ${metrics.dataset.n_agents} synthetic agents × ${metrics.dataset.n_steps} steps.`
                  : undefined
              }
            />
            {!metrics ? (
              <p className="p-6 text-body-sm text-on-surface-variant">
                No trained model on disk — scores are the Phase 3 heuristic.
                Run <code className="text-primary">python -m app.ml.train</code> to
                enable ML scoring.
              </p>
            ) : (
              <div className="flex flex-col divide-y divide-white/5">
                <div className="flex items-center justify-between px-6 py-3">
                  <span className="text-body-sm text-on-surface-variant">
                    Trust scoring (AUC)
                  </span>
                  <span className="font-mono text-body-sm">
                    <span className="text-outline">
                      {metrics.trust_model.baseline_auc.toFixed(3)}
                    </span>
                    <span className="mx-1.5 text-outline">→</span>
                    <span className="text-tertiary">
                      {metrics.trust_model.learned_auc.toFixed(3)}
                    </span>
                  </span>
                </div>
                <div className="flex items-center justify-between px-6 py-3">
                  <span className="text-body-sm text-on-surface-variant">
                    Anomaly detection (F1)
                  </span>
                  <span className="font-mono text-body-sm">
                    <span className="text-outline">
                      {metrics.anomaly_detection.baseline.f1.toFixed(3)}
                    </span>
                    <span className="mx-1.5 text-outline">→</span>
                    <span className="text-tertiary">
                      {metrics.anomaly_detection.learned.f1.toFixed(3)}
                    </span>
                  </span>
                </div>
                <div className="flex items-center justify-between px-6 py-3">
                  <span className="text-body-sm text-on-surface-variant">
                    Simulation (log-loss, lower is better)
                  </span>
                  <span className="font-mono text-body-sm">
                    <span className="text-outline">
                      {metrics.simulation_model.baseline_log_loss.toFixed(3)}
                    </span>
                    <span className="mx-1.5 text-outline">→</span>
                    <span className="text-tertiary">
                      {metrics.simulation_model.learned_log_loss.toFixed(3)}
                    </span>
                  </span>
                </div>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
