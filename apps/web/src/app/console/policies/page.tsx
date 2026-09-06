import { AlertTriangle, BadgeCheck, Gavel, Pause, ShieldX, UserSearch } from "lucide-react";

import { RuleBuilder } from "@/components/policy/rule-builder";
import { ApiError, EmptyState } from "@/components/ui/api-error";
import { DataTable, type Column } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import { fetchPolicyDetails, fetchRuleVocabulary, tryFetch } from "@/lib/api";
import type { PolicyDetail, Severity } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";

export const metadata = { title: "Policy Governance — ATLAS" };
export const dynamic = "force-dynamic";

const SEVERITY_TONE: Record<Severity, ChipTone> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
};

const EMERGENCY_CONTROLS = [
  {
    label: "Pause AI Agent",
    icon: Pause,
    tone: "border-brand-amber/40 text-brand-amber hover:bg-brand-amber/10",
  },
  {
    label: "Force Human Review",
    icon: UserSearch,
    tone: "border-secondary/40 text-secondary hover:bg-secondary/10",
  },
  {
    label: "Emergency Lockdown",
    icon: ShieldX,
    tone: "border-error/40 text-error hover:bg-error/10",
  },
];

function RuleSummary({ policy }: { policy: PolicyDetail }) {
  if (!policy.rule) {
    return <p className="font-mono text-status-label text-outline">No active rule</p>;
  }
  const [condition, effect] = policy.summary;
  return (
    <div className="mt-1 flex flex-col gap-0.5">
      <p className="font-mono text-status-label text-on-surface-variant">{condition}</p>
      <p className="font-mono text-status-label text-primary">{effect}</p>
    </div>
  );
}

const POLICY_COLUMNS: Column<PolicyDetail>[] = [
  {
    key: "policy",
    header: "Policy / rule",
    width: "49%",
    cell: (policy) => (
      <>
        <div className="flex items-baseline gap-2">
          <p className="truncate text-body-md text-on-surface">{policy.name}</p>
          <span className="shrink-0 font-mono text-label-mono-xs text-outline">
            {policy.version}
          </span>
        </div>
        <RuleSummary policy={policy} />
      </>
    ),
  },
  {
    key: "severity",
    header: "Severity",
    width: "13%",
    cell: (policy) => (
      <StatusChip tone={SEVERITY_TONE[policy.severity]}>{policy.severity}</StatusChip>
    ),
  },
  {
    key: "violations",
    header: "Violations 24h",
    align: "right",
    width: "16%",
    cell: (policy) => (
      <>
        <span
          className={
            policy.violations24h > 0
              ? "font-mono text-body-sm text-error"
              : "font-mono text-body-sm text-on-surface-variant"
          }
        >
          {policy.violations24h}
        </span>
        {/* The denominator, always: 3 of 8 is noise, 3 of 8,000 is a finding. */}
        <span className="ml-1.5 font-mono text-label-mono-xs text-outline">
          of {policy.evaluations24h.toLocaleString("en-US")}
        </span>
      </>
    ),
  },
  {
    key: "updated",
    header: "Updated",
    align: "right",
    width: "11%",
    hideBelow: "lg",
    cell: (policy) => (
      <span className="font-mono text-label-mono-xs text-outline">
        {formatDate(policy.updatedAt)}
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    width: "11%",
    cell: (policy) => (
      <StatusChip tone={policy.enabled ? "success" : "neutral"}>
        {policy.enabled ? "Active" : "Paused"}
      </StatusChip>
    ),
  },
];

export default async function PolicyGovernancePage() {
  const [policiesResult, vocabularyResult] = await Promise.all([
    tryFetch(fetchPolicyDetails),
    tryFetch(fetchRuleVocabulary),
  ]);

  if (!policiesResult.ok) {
    return (
      <>
        <PageHeader
          eyebrow="Governance"
          title="Policies"
          description="Context-aware governance powered by live trust signals and policy-as-code."
        />
        <ApiError error={policiesResult.error} />
      </>
    );
  }

  const policies = policiesResult.data;
  const vocabulary = vocabularyResult.ok ? vocabularyResult.data : null;
  const active = policies.filter((p) => p.enabled);
  const criticalCount = policies.filter((p) => p.severity === "critical").length;
  const violations = policies.reduce((sum, p) => sum + p.violations24h, 0);
  const evaluations = policies.reduce((sum, p) => sum + p.evaluations24h, 0);
  const complianceRate = evaluations > 0 ? (1 - violations / evaluations) * 100 : 100;

  // The rule shown in the builder by default — the one the original design
  // depicted, if it is still present.
  const seedRule = policies.find((p) => p.id === "pol-14")?.rule ?? active[0]?.rule ?? null;

  return (
    <>
      <PageHeader
        eyebrow="Governance"
        title="Policies"
        description="Rules are structured data, not code — versioned, evaluable, and simulatable against recorded decisions before they govern anything."
      />

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Active Policies"
          value={String(active.length)}
          icon={Gavel}
          tone="secondary"
        />
        <StatCard
          label="Critical Rules"
          value={String(criticalCount)}
          icon={AlertTriangle}
          tone="error"
        />
        <StatCard
          label="Compliance Rate"
          value={`${complianceRate.toFixed(2)}%`}
          icon={BadgeCheck}
          tone="tertiary"
        />
        <StatCard
          label="Violations (24h)"
          value={String(violations)}
          icon={ShieldX}
          tone="primary"
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          {vocabulary ? (
            <RuleBuilder vocabulary={vocabulary} initialRule={seedRule} />
          ) : (
            <Panel>
              <PanelHeader title="Rule Builder" />
              <p className="px-4 py-3.5 text-body-md text-on-surface-variant">
                Rule vocabulary unavailable — the builder needs the API to tell it which
                fields and operators the engine accepts.
              </p>
            </Panel>
          )}

          <Panel>
            <PanelHeader
              title="Policy ledger"
              description="Every policy version is immutable; editing appends a new one."
            />
            <DataTable
              columns={POLICY_COLUMNS}
              rows={policies}
              rowKey={(policy) => policy.id}
              fixed
              minWidthClass="md:min-w-[46rem]"
              empty={<EmptyState title="No policies defined" />}
            />
          </Panel>
        </div>

        <div className="flex flex-col gap-4 xl:sticky xl:top-[76px] xl:col-span-4">
          <Panel>
            <PanelHeader
              title="Emergency Controls"
              icon={AlertTriangle}
              description="Override standard automated governance in critical scenarios."
            />
            <div className="flex flex-col gap-2 px-4 py-3.5">
              {EMERGENCY_CONTROLS.map((control) => (
                <button
                  key={control.label}
                  type="button"
                  className={cn(
                    "flex items-center gap-2.5 rounded-md border px-3 py-2 text-body-sm transition-colors",
                    control.tone,
                  )}
                >
                  <control.icon className="size-4 shrink-0" />
                  {control.label}
                </button>
              ))}
              <p className="eyebrow mt-1">Requires auth token</p>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Rule Vocabulary"
              description="The closed set of fields a rule may reference."
            />
            {vocabulary ? (
              <ul className="custom-scrollbar max-h-[26rem] divide-y divide-outline-variant overflow-y-auto">
                {vocabulary.fields.map((field) => (
                  <li key={field.key} className="px-4 py-2.5">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-body-sm text-on-surface">{field.label}</span>
                      <span className="font-mono text-label-mono-xs text-outline">
                        {field.kind}
                      </span>
                    </div>
                    <p className="mt-0.5 text-body-sm text-outline">{field.description}</p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-4 py-3.5 text-body-md text-on-surface-variant">Unavailable.</p>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
