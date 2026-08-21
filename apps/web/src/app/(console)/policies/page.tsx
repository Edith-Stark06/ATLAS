import { AlertTriangle, BadgeCheck, Gavel, Pause, ShieldX, UserSearch } from "lucide-react";

import { RuleBuilder } from "@/components/policy/rule-builder";
import { ApiError } from "@/components/ui/api-error";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import { fetchPolicyDetails, fetchRuleVocabulary, tryFetch } from "@/lib/api";
import type { PolicyDetail, Severity } from "@/lib/types";
import { formatDate } from "@/lib/utils";

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

export default async function PolicyGovernancePage() {
  const [policiesResult, vocabularyResult] = await Promise.all([
    tryFetch(fetchPolicyDetails),
    tryFetch(fetchRuleVocabulary),
  ]);

  if (!policiesResult.ok) {
    return (
      <>
        <PageHeader
          title="Policy"
          highlight="Governance"
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
        title="Policy"
        highlight="Governance"
        description="Rules are structured data, not code — versioned, evaluable, and simulatable against recorded decisions before they govern anything."
      />

      <div className="mb-stack-md grid grid-cols-2 gap-4 lg:grid-cols-4">
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

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          {vocabulary ? (
            <RuleBuilder vocabulary={vocabulary} initialRule={seedRule} />
          ) : (
            <Panel>
              <PanelHeader title="Rule Builder" />
              <p className="p-6 text-body-sm text-on-surface-variant">
                Rule vocabulary unavailable — the builder needs the API to tell it which
                fields and operators the engine accepts.
              </p>
            </Panel>
          )}

          <Panel>
            <PanelHeader
              title="Policy Ledger"
              description="Every policy version is immutable; editing appends a new one."
            />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] border-collapse">
                <thead>
                  <tr className="border-b border-white/5">
                    {["Policy / Rule", "Severity", "Violations (24h)", "Updated", "Status"].map(
                      (col) => (
                        <th
                          key={col}
                          scope="col"
                          className="px-6 py-3 text-left font-mono text-status-label uppercase text-on-surface-variant"
                        >
                          {col}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {policies.map((policy) => (
                    <tr key={policy.id} className="transition-colors hover:bg-surface-variant/20">
                      <td className="px-6 py-4">
                        <div className="flex items-baseline gap-2">
                          <p className="text-body-md text-on-surface">{policy.name}</p>
                          <span className="font-mono text-status-label text-outline">
                            {policy.version}
                          </span>
                        </div>
                        <RuleSummary policy={policy} />
                      </td>
                      <td className="px-6 py-4">
                        <StatusChip tone={SEVERITY_TONE[policy.severity]}>
                          {policy.severity}
                        </StatusChip>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={
                            policy.violations24h > 0
                              ? "font-mono text-body-sm text-error"
                              : "font-mono text-body-sm text-on-surface-variant"
                          }
                        >
                          {policy.violations24h}
                        </span>
                        <span className="ml-2 font-mono text-status-label text-outline">
                          of {policy.evaluations24h.toLocaleString("en-US")}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-status-label text-outline">
                        {formatDate(policy.updatedAt)}
                      </td>
                      <td className="px-6 py-4">
                        <StatusChip tone={policy.enabled ? "success" : "neutral"}>
                          {policy.enabled ? "Active" : "Paused"}
                        </StatusChip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        <div className="flex flex-col gap-4 xl:col-span-4">
          <Panel>
            <PanelHeader
              title="Emergency Controls"
              icon={AlertTriangle}
              description="Override standard automated governance in critical scenarios."
            />
            <div className="flex flex-col gap-3 p-6">
              {EMERGENCY_CONTROLS.map((control) => (
                <button
                  key={control.label}
                  type="button"
                  className={`flex items-center gap-3 rounded border bg-transparent px-4 py-3 text-body-sm transition-colors ${control.tone}`}
                >
                  <control.icon className="size-4 shrink-0" />
                  {control.label}
                </button>
              ))}
              <p className="mt-1 font-mono text-status-label uppercase text-outline">
                Requires auth token
              </p>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Rule Vocabulary"
              description="The closed set of fields a rule may reference."
            />
            {vocabulary ? (
              <ul className="divide-y divide-white/5">
                {vocabulary.fields.map((field) => (
                  <li key={field.key} className="px-6 py-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-body-sm text-on-surface">{field.label}</span>
                      <span className="font-mono text-status-label text-outline">
                        {field.kind}
                      </span>
                    </div>
                    <p className="mt-0.5 text-status-label text-on-surface-variant">
                      {field.description}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-6 text-body-sm text-on-surface-variant">Unavailable.</p>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
