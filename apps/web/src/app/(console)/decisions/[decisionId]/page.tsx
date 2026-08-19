import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  Bot,
  Check,
  Gavel,
  GitBranch,
  ShieldAlert,
  TriangleAlert,
  X,
} from "lucide-react";

import { trustColor } from "@/components/ui/lifecycle-badge";
import { OutcomeBadge, riskColor } from "@/components/ui/outcome-badge";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Pipeline } from "@/components/ui/pipeline";
import { StatusChip } from "@/components/ui/status-chip";
import { DECISIONS, getDecision } from "@/lib/mock-data";
import type { RiskVector } from "@/lib/types";
import { cn, formatTime, formatUsd } from "@/lib/utils";

export function generateStaticParams() {
  return DECISIONS.map((d) => ({ decisionId: d.id }));
}

const RISK_LABELS: { key: keyof RiskVector; label: string }[] = [
  { key: "financial", label: "Financial" },
  { key: "fraud", label: "Fraud" },
  { key: "operational", label: "Operational" },
  { key: "regulatory", label: "Regulatory" },
];

function riskBar(score: number): string {
  if (score >= 75) return "bg-error";
  if (score >= 50) return "bg-brand-amber";
  if (score >= 25) return "bg-primary";
  return "bg-tertiary";
}

export default async function DecisionInvestigationPage({
  params,
}: {
  params: Promise<{ decisionId: string }>;
}) {
  const { decisionId } = await params;
  const decision = getDecision(decisionId);
  if (!decision) notFound();

  const investigation = decision.investigation;
  const failedChecks = decision.policyChecks.filter((c) => !c.passed);

  return (
    <>
      <Link
        href="/decisions"
        className="mb-4 inline-flex items-center gap-2 font-mono text-label-mono text-on-surface-variant transition-colors hover:text-primary"
      >
        <ArrowLeft className="size-4" />
        All decisions
      </Link>

      <div className="mb-stack-lg flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <span className="rounded bg-surface-variant px-2 py-1 font-mono text-status-label text-on-surface-variant">
              ID: {decision.id}
            </span>
            <span className="flex items-center gap-1.5 font-mono text-label-mono text-on-surface-variant">
              <Bot className="size-4 text-secondary" />
              {decision.agentName}
            </span>
            <OutcomeBadge outcome={decision.outcome} />
          </div>
          <h1 className="text-headline-lg text-on-surface">Decision Investigation</h1>
          <p className="mt-1 text-body-md text-on-surface-variant">{decision.action}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="flex items-center gap-2 rounded border border-error/40 px-3 py-2 text-body-sm text-error transition-colors hover:bg-error/10"
          >
            <X className="size-4" /> Reject
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded border border-tertiary/40 px-3 py-2 text-body-sm text-tertiary transition-colors hover:bg-tertiary/10"
          >
            <Check className="size-4" /> Approve
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded border border-primary/40 px-3 py-2 text-body-sm text-primary transition-colors hover:bg-primary/10"
          >
            <Gavel className="size-4" /> Escalate Review
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          <Panel>
            <PanelHeader
              title={
                decision.outcome === "approved"
                  ? "Why was this approved?"
                  : "Why was this blocked?"
              }
              icon={ShieldAlert}
            />
            <div className="flex flex-col gap-5 p-6">
              <p className="text-body-md text-on-surface-variant">
                {investigation?.summary ?? decision.rationale}
              </p>

              {investigation && investigation.criticalFactors.length > 0 && (
                <div>
                  <h3 className="mb-3 font-mono text-label-mono uppercase text-on-surface-variant">
                    Critical Factors
                  </h3>
                  <ul className="flex flex-col gap-3">
                    {investigation.criticalFactors.map((factor) => (
                      <li
                        key={factor.key}
                        className="flex gap-3 rounded-lg border border-white/5 bg-surface-container-high/50 p-4"
                      >
                        <TriangleAlert
                          className={cn(
                            "mt-0.5 size-4 shrink-0",
                            factor.severity === "critical" ? "text-error" : "text-brand-amber",
                          )}
                        />
                        <div>
                          <p className="text-body-md text-on-surface">{factor.title}</p>
                          <p className="mt-1 text-body-sm text-on-surface-variant">
                            {factor.detail}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {investigation?.actionRequired && (
                <p className="rounded border-l-2 border-primary bg-primary/5 px-4 py-3 text-body-sm text-on-surface">
                  <span className="font-mono text-label-mono uppercase text-primary">
                    Action required:{" "}
                  </span>
                  {investigation.actionRequired}
                </p>
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Decision Flow Trace" icon={GitBranch} />
            <div className="p-6">
              <Pipeline
                stages={
                  investigation?.trace ?? [
                    { key: "request", label: "Ingestion", status: "done" },
                    { key: "policy", label: "Validation", status: "done" },
                    { key: "trust", label: "Model Eval", status: "done" },
                    { key: "simulation", label: "Risk Assessment", status: "done" },
                    { key: "ledger", label: "Gov Ledger", status: "done" },
                  ]
                }
              />
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Policy Evidence"
              description={`${failedChecks.length} of ${decision.policyChecks.length} policies failed.`}
            />
            <ul className="divide-y divide-white/5">
              {decision.policyChecks.map((check) => (
                <li key={check.policyId} className="flex items-center gap-4 px-6 py-3.5">
                  {check.passed ? (
                    <Check className="size-4 shrink-0 text-tertiary" />
                  ) : (
                    <X className="size-4 shrink-0 text-error" />
                  )}
                  <span className="w-56 shrink-0 text-body-sm text-on-surface">
                    {check.policyName}
                  </span>
                  <span className="min-w-0 flex-1 text-body-sm text-on-surface-variant">
                    {check.detail ?? "—"}
                  </span>
                  <StatusChip tone={check.passed ? "success" : "danger"}>
                    {check.passed ? "Pass" : "Fail"}
                  </StatusChip>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <Panel>
            <PanelHeader title="Trust State" />
            <div className="flex flex-col gap-4 p-6">
              <div className="flex items-end justify-between">
                <div>
                  <span
                    className={cn("text-headline-lg", trustColor(decision.trustScore))}
                  >
                    {decision.trustScore}
                  </span>
                  <span className="font-mono text-label-mono text-outline">/100</span>
                </div>
                {investigation && (
                  <span className="font-mono text-label-mono text-error">
                    ▼ {investigation.trustBefore} → {decision.trustScore}
                  </span>
                )}
              </div>
              <div className="flex items-center justify-between border-t border-white/5 pt-4">
                <span className="text-body-sm text-on-surface-variant">Model Certainty</span>
                <span className="font-mono text-body-md text-on-surface">
                  {investigation?.confidence ?? 99}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body-sm text-on-surface-variant">Decision Latency</span>
                <span className="font-mono text-body-md text-on-surface">
                  {decision.latencyMs}ms
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body-sm text-on-surface-variant">Amount</span>
                <span className="font-mono text-body-md text-on-surface">
                  {formatUsd(decision.amountUsd)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-body-sm text-on-surface-variant">Decided</span>
                <span className="font-mono text-body-md text-on-surface">
                  {formatTime(decision.decidedAt)}
                </span>
              </div>
            </div>
          </Panel>

          {investigation && (
            <Panel>
              <PanelHeader
                title="Risk Analysis Vector"
                action={
                  <StatusChip tone={riskColor(decision.riskScore) === "text-error" ? "danger" : "info"}>
                    {decision.riskScore >= 75 ? "High Risk" : "Moderate"}
                  </StatusChip>
                }
              />
              <div className="flex flex-col gap-4 p-6">
                {RISK_LABELS.map(({ key, label }) => {
                  const score = investigation.riskVector[key];
                  return (
                    <div key={key}>
                      <div className="mb-1.5 flex items-baseline justify-between">
                        <span className="text-body-sm text-on-surface-variant">{label}</span>
                        <span className={cn("font-mono text-body-sm", riskColor(score))}>
                          {score}%
                        </span>
                      </div>
                      <div className="h-1 w-full overflow-hidden rounded-full bg-surface-container-high">
                        <div
                          className={cn("h-full rounded-full", riskBar(score))}
                          style={{ width: `${score}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
