import Link from "next/link";
import { Cpu, Fingerprint, RefreshCw, ScrollText } from "lucide-react";

import { runReloadModels } from "@/app/console/models/actions";
import { ApiError, EmptyState } from "@/components/ui/api-error";
import { Meter } from "@/components/ui/charts";
import { PageHeader, SectionHeader } from "@/components/ui/page-header";
import { Button, Panel, PanelFooter, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchLedgerStats, fetchModelInfo, tryFetch } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

export const metadata = { title: "Model Lifecycle — ATLAS" };
export const dynamic = "force-dynamic";

/**
 * The shape `python -m app.ml.train` writes to metrics.json. Read defensively —
 * a partial retrain (the trust model without the risk model, say) leaves some
 * of these absent, and the page has to say so rather than render NaN.
 */
interface ModelMetrics {
  trained_at?: string;
  trust_model?: { baseline_auc: number; learned_auc: number; auc_improvement_pct: number };
  anomaly_detection?: {
    baseline: { precision: number; recall: number; f1: number };
    learned: { precision: number; recall: number; f1: number };
  };
  simulation_model?: {
    baseline_accuracy: number;
    learned_accuracy: number;
    baseline_log_loss: number;
    learned_log_loss: number;
  };
  risk_model?: Record<string, unknown>;
  dataset?: { n_agents: number; n_steps: number };
}

/**
 * One learned-vs-baseline comparison. Direction matters: log-loss improves
 * downward, every other metric here improves upward.
 */
function Comparison({
  label,
  baseline,
  learned,
  lowerIsBetter = false,
  detail,
}: {
  label: string;
  baseline: number;
  learned: number;
  lowerIsBetter?: boolean;
  detail?: string;
}) {
  const better = lowerIsBetter ? learned < baseline : learned > baseline;
  // Both bars share a scale so the pair is comparable at a glance.
  const scale = Math.max(baseline, learned, 0.0001);

  return (
    <div className="px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-body-md text-on-surface">{label}</span>
        <span className="font-mono text-body-sm">
          <span className="text-outline">{baseline.toFixed(3)}</span>
          <span className="mx-1.5 text-outline">→</span>
          <span className={better ? "text-tertiary" : "text-brand-amber"}>
            {learned.toFixed(3)}
          </span>
        </span>
      </div>

      <div className="mt-2 space-y-1">
        <div className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-label-mono-xs text-outline">baseline</span>
          <Meter value={baseline} max={scale} color="bg-outline-strong" />
        </div>
        <div className="flex items-center gap-2">
          <span className="w-14 shrink-0 text-label-mono-xs text-outline">learned</span>
          <Meter
            value={learned}
            max={scale}
            color={better ? "bg-tertiary" : "bg-brand-amber"}
          />
        </div>
      </div>

      {detail && <p className="mt-1.5 text-body-sm text-outline">{detail}</p>}
    </div>
  );
}

const PROMOTION_STEPS = [
  {
    step: "Train a candidate",
    detail:
      "Building with an explicit output directory and seed makes the candidate genuinely different from what is live, rather than a reproduction of it — training is otherwise fully deterministic.",
  },
  {
    step: "Compare against live",
    detail:
      "Promotion compares the candidate's metrics against the live set on every measure above, and refuses a regression past tolerance without an explicit override and a stated reason.",
  },
  {
    step: "Swap with a backup",
    detail:
      "The candidate is overlaid onto a timestamped backup of what was live, so an artifact the candidate never trained is preserved rather than deleted.",
  },
  {
    step: "Reload without a restart",
    detail:
      "Reloading clears the cached loaders so the running process picks up the new artifacts, and the next decision pins the fingerprint that actually scored it.",
  },
  {
    step: "Roll back if needed",
    detail: "Rollback restores the backup taken at promotion time.",
  },
];

export default async function ModelLifecyclePage() {
  const [modelResult, ledgerResult] = await Promise.all([
    tryFetch(fetchModelInfo),
    tryFetch(fetchLedgerStats),
  ]);

  const header = (
    <PageHeader
      eyebrow="System"
      title="Model lifecycle"
      description="Which models are deciding right now, how they measured against the heuristic they replaced, and what is pinned into the decisions they scored."
      action={
        // A form POST, not a link: this swaps the live scoring artifacts. The
        // API requires an admin token and rejects anyone else.
        <form action={runReloadModels}>
          <Button type="submit" variant="secondary">
            <RefreshCw className="size-3.5" />
            Reload artifacts
          </Button>
        </form>
      }
    />
  );

  if (!modelResult.ok) {
    return (
      <>
        {header}
        <ApiError error={modelResult.error} />
      </>
    );
  }

  const info = modelResult.data;
  const metrics = (info.metrics ?? null) as ModelMetrics | null;
  const ledger = ledgerResult.ok ? ledgerResult.data : null;
  const fingerprint = ledger?.modelFingerprint ?? null;

  if (!info.available || !metrics) {
    return (
      <>
        {header}
        <Panel>
          <EmptyState
            icon={Cpu}
            title="No trained model on disk"
            description="Scores are coming from the heuristic fallback. Train a candidate to put a learned model in front of decisions."
          />
          <PanelFooter>
            <code className="font-mono text-label-mono text-on-surface">
              python -m app.ml.train
            </code>{" "}
            writes artifacts and a metrics file;{" "}
            <code className="font-mono text-label-mono text-on-surface">
              python -m app.ml.promote
            </code>{" "}
            compares a candidate against what is live and refuses a regression.
          </PanelFooter>
        </Panel>
      </>
    );
  }

  const trained = metrics.trained_at ? formatDate(metrics.trained_at) : "unknown";
  const trustImprovement = metrics.trust_model?.auc_improvement_pct;

  return (
    <>
      {header}

      <div className="mb-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard
          label="Status"
          value="Live"
          icon={Cpu}
          tone="tertiary"
          hint="serving decisions"
          featured
        />
        <StatCard label="Trained" value={trained} hint="artifacts on disk" />
        <StatCard
          label="Trust model lift"
          value={trustImprovement === undefined ? "—" : `${trustImprovement.toFixed(1)}%`}
          hint="AUC vs. heuristic"
          tone={trustImprovement !== undefined && trustImprovement > 0 ? "tertiary" : "warning"}
        />
        <StatCard
          label="Training set"
          value={
            metrics.dataset ? `${metrics.dataset.n_agents}×${metrics.dataset.n_steps}` : "—"
          }
          hint={metrics.dataset ? "agents × steps" : "not recorded"}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="flex flex-col gap-4 xl:col-span-2">
          <Panel>
            <PanelHeader
              title="Evaluation"
              description="Measured on held-out data by the training run itself — read back from what it recorded, never asserted here."
            />
            <div className="divide-y divide-outline-variant">
              {metrics.trust_model && (
                <Comparison
                  label="Trust scoring"
                  baseline={metrics.trust_model.baseline_auc}
                  learned={metrics.trust_model.learned_auc}
                  detail="AUC — how well the score separates compliant behaviour from the rest. Higher is better."
                />
              )}
              {metrics.anomaly_detection && (
                <Comparison
                  label="Anomaly detection"
                  baseline={metrics.anomaly_detection.baseline.f1}
                  learned={metrics.anomaly_detection.learned.f1}
                  detail={`F1 — precision ${metrics.anomaly_detection.learned.precision.toFixed(3)}, recall ${metrics.anomaly_detection.learned.recall.toFixed(3)}. Higher is better.`}
                />
              )}
              {metrics.simulation_model && (
                <>
                  <Comparison
                    label="Outcome prediction"
                    baseline={metrics.simulation_model.baseline_accuracy}
                    learned={metrics.simulation_model.learned_accuracy}
                    detail="Accuracy on held-out decisions. Higher is better."
                  />
                  <Comparison
                    label="Outcome calibration"
                    baseline={metrics.simulation_model.baseline_log_loss}
                    learned={metrics.simulation_model.learned_log_loss}
                    lowerIsBetter
                    detail="Log loss — penalises confident wrong answers. Lower is better."
                  />
                </>
              )}
            </div>
            <PanelFooter>
              Every figure above compares the model against the hand-set heuristic it
              replaced. A candidate that loses on any of them does not get promoted.
            </PanelFooter>
          </Panel>

          <div>
            <SectionHeader
              title="Promotion"
              description="How a candidate becomes the model that decides."
            />
            <Panel>
              <ol className="divide-y divide-outline-variant">
                {PROMOTION_STEPS.map((item, index) => (
                  <li key={item.step} className="flex gap-3 px-4 py-3">
                    <span className="mt-0.5 font-mono text-label-mono-xs text-outline">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div className="min-w-0">
                      <p className="text-body-md text-on-surface">{item.step}</p>
                      <p className="mt-0.5 text-body-sm text-on-surface-variant">
                        {item.detail}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
              <PanelFooter>
                There is no live traffic-split canary — routing a share of real requests to a
                candidate needs weighted routing across replicas. Comparison-gated promotion
                serves the same &ldquo;do not ship a worse model&rdquo; goal without it.
              </PanelFooter>
            </Panel>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <Panel>
            <PanelHeader title="Live artifacts" icon={Fingerprint} />
            <dl className="divide-y divide-outline-variant">
              <div className="px-4 py-3">
                <dt className="eyebrow">Fingerprint</dt>
                <dd className="mt-1 break-all font-mono text-body-sm text-on-surface">
                  {fingerprint ?? "not recorded"}
                </dd>
                <p className="mt-1.5 text-body-sm text-on-surface-variant">
                  SHA-256 of the artifacts on disk. A decision whose pinned fingerprint differs
                  from this was made by a different model.
                </p>
              </div>
              <div className="flex items-center justify-between gap-3 px-4 py-2.5">
                <dt className="text-body-sm text-on-surface-variant">Trained at</dt>
                <dd className="font-mono text-body-sm text-on-surface">{trained}</dd>
              </div>
              <div className="flex items-center justify-between gap-3 px-4 py-2.5">
                <dt className="text-body-sm text-on-surface-variant">Serving</dt>
                <dd>
                  <StatusChip tone="success">Active</StatusChip>
                </dd>
              </div>
            </dl>
          </Panel>

          <Panel>
            <PanelHeader
              title="Components"
              description="What is loaded, and what each one decides."
            />
            <ul className="divide-y divide-outline-variant">
              {[
                {
                  name: "trust_model",
                  role: "Scores each agent's trust",
                  present: Boolean(metrics.trust_model),
                },
                {
                  name: "anomaly_detector",
                  role: "Flags behaviour unlike an agent's own history",
                  present: Boolean(metrics.anomaly_detection),
                },
                {
                  name: "simulation_model",
                  role: "Predicts the outcome of a proposed action",
                  present: Boolean(metrics.simulation_model),
                },
                {
                  name: "risk_model",
                  role: "Scores risk from real transaction data",
                  present: Boolean(metrics.risk_model),
                },
              ].map((component) => (
                <li key={component.name} className="flex items-center gap-3 px-4 py-2.5">
                  <span
                    className={cn(
                      "size-1.5 shrink-0 rounded-full",
                      component.present ? "bg-tertiary" : "bg-outline",
                    )}
                    aria-hidden
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block font-mono text-label-mono text-on-surface">
                      {component.name}
                    </span>
                    <span className="block truncate text-body-sm text-outline">
                      {component.role}
                    </span>
                  </span>
                  <StatusChip tone={component.present ? "success" : "neutral"}>
                    {component.present ? "Loaded" : "Absent"}
                  </StatusChip>
                </li>
              ))}
            </ul>
            <PanelFooter>
              &ldquo;Absent&rdquo; means the last training run recorded no metrics for that
              component — not that decisions are ungoverned. Every component has a heuristic
              fallback.
            </PanelFooter>
          </Panel>

          <Panel>
            <PanelHeader title="Where models show up" />
            <div className="divide-y divide-outline-variant">
              {[
                {
                  href: "/console/trust-engine",
                  icon: Cpu,
                  label: "Trust & risk",
                  detail: "The scores this model produces, per agent",
                },
                {
                  href: "/console/ledger",
                  icon: ScrollText,
                  label: "Ledger",
                  detail: "The fingerprint pinned into each decision",
                },
                {
                  href: "/console/simulations",
                  icon: Fingerprint,
                  label: "Simulation",
                  detail: "Outcome predictions from the same artifacts",
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
