import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Brain,
  Gavel,
  Pause,
  ShieldX,
  UserSearch,
  Wallet,
} from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip, type ChipTone } from "@/components/ui/status-chip";
import { ApiError } from "@/components/ui/api-error";
import { fetchPolicies, tryFetch } from "@/lib/api";
import type { Severity } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export const metadata = { title: "Policy Governance — ATLAS" };
export const dynamic = "force-dynamic";

const SEVERITY_TONE: Record<Severity, ChipTone> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
};

const RULE_META = [
  { label: "Policy Version", value: "v2.4.1-stable" },
  { label: "Policy Owner", value: "SecOps Team" },
  { label: "OPA Policy Status", value: "Synced" },
  { label: "Rule Simulation", value: "Passed" },
];

const EMERGENCY_CONTROLS = [
  { label: "Pause AI Agent", icon: Pause, tone: "border-brand-amber/40 text-brand-amber hover:bg-brand-amber/10" },
  { label: "Force Human Review", icon: UserSearch, tone: "border-secondary/40 text-secondary hover:bg-secondary/10" },
  { label: "Emergency Lockdown", icon: ShieldX, tone: "border-error/40 text-error hover:bg-error/10" },
];

const TRUST_DISTRIBUTION = [
  { label: "High Confidence", pct: 82, bar: "bg-tertiary" },
  { label: "Needs Verification", pct: 15, bar: "bg-brand-amber" },
  { label: "Flagged", pct: 3, bar: "bg-error" },
];

/** Visual representation of the active rule; authoring lands in Phase 4. */
function RuleClause({
  keyword,
  icon: Icon,
  subject,
  operator,
  value,
}: {
  keyword: string;
  icon: React.ComponentType<{ className?: string }>;
  subject: string;
  operator?: string;
  value?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="w-12 shrink-0 font-mono text-label-mono uppercase text-primary">
        {keyword}
      </span>
      <span className="flex items-center gap-2 rounded border border-white/10 bg-surface-container-high px-3 py-2">
        <Icon className="size-4 text-secondary" />
        <span className="text-body-sm text-on-surface">{subject}</span>
        {operator && (
          <span className="font-mono text-label-mono text-on-surface-variant">{operator}</span>
        )}
        {value && <span className="font-mono text-body-sm text-primary">{value}</span>}
      </span>
    </div>
  );
}

export default async function PolicyGovernancePage() {
  const result = await tryFetch(fetchPolicies);

  if (!result.ok) {
    return (
      <>
        <PageHeader
          title="Policy"
          highlight="Governance"
          description="Context-aware governance powered by live trust signals and policy-as-code."
        />
        <ApiError error={result.error} />
      </>
    );
  }

  const POLICIES = result.data;
  const criticalCount = POLICIES.filter((p) => p.severity === "critical").length;
  const violations = POLICIES.reduce((sum, p) => sum + p.violations24h, 0);

  return (
    <>
      <PageHeader
        title="Policy"
        highlight="Governance"
        description="Context-aware governance powered by live trust signals and policy-as-code."
      />

      <div className="mb-stack-md grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Active Policies" value={String(POLICIES.filter((p) => p.enabled).length)} icon={Gavel} tone="secondary" />
        <StatCard label="Critical Rules" value={String(criticalCount)} icon={AlertTriangle} tone="error" />
        <StatCard label="Compliance Rate" value="99.98%" icon={BadgeCheck} tone="tertiary" />
        <StatCard label="Violations (24h)" value={String(violations)} icon={ShieldX} tone="primary" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-8">
          <Panel>
            <PanelHeader
              title="Policy Brain Builder"
              icon={Brain}
              description="The rule currently governing high-value autonomous approvals."
              action={<GhostButton>Deploy Rule</GhostButton>}
            />
            <div className="flex flex-col gap-4 p-6">
              <RuleClause keyword="If" icon={BadgeCheck} subject="Trust Score" operator="<" value="70" />
              <RuleClause keyword="And" icon={Wallet} subject="Transaction" operator=">" value="$5,000" />
              <div className="flex items-center gap-3 pl-12">
                <ArrowRight className="size-4 text-outline" />
              </div>
              <RuleClause keyword="Then" icon={UserSearch} subject="Require Human Review" />

              <dl className="mt-2 grid grid-cols-2 gap-4 border-t border-white/5 pt-4 lg:grid-cols-4">
                {RULE_META.map((meta) => (
                  <div key={meta.label}>
                    <dt className="font-mono text-status-label uppercase text-on-surface-variant">
                      {meta.label}
                    </dt>
                    <dd className="mt-1 font-mono text-body-sm text-on-surface">{meta.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </Panel>

          <Panel>
            <PanelHeader title="Policy Ledger" description="Every policy version is immutable and auditable." />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse">
                <thead>
                  <tr className="border-b border-white/5">
                    {["Policy Name", "Scope", "Severity", "Violations (24h)", "Updated", "Status"].map(
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
                  {POLICIES.map((policy) => (
                    <tr key={policy.id} className="transition-colors hover:bg-surface-variant/20">
                      <td className="px-6 py-4">
                        <p className="text-body-md text-on-surface">{policy.name}</p>
                        <p className="font-mono text-status-label text-outline">{policy.version}</p>
                      </td>
                      <td className="px-6 py-4 text-body-sm text-on-surface-variant">{policy.scope}</td>
                      <td className="px-6 py-4">
                        <StatusChip tone={SEVERITY_TONE[policy.severity]}>{policy.severity}</StatusChip>
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
            <PanelHeader title="Trust Distribution" description="Share of decisions by confidence band." />
            <div className="flex flex-col gap-4 p-6">
              {TRUST_DISTRIBUTION.map((band) => (
                <div key={band.label}>
                  <div className="mb-1.5 flex items-baseline justify-between">
                    <span className="text-body-sm text-on-surface-variant">{band.label}</span>
                    <span className="font-mono text-body-sm text-on-surface">{band.pct}%</span>
                  </div>
                  <div className="h-1 w-full overflow-hidden rounded-full bg-surface-container-high">
                    <div className={`h-full rounded-full ${band.bar}`} style={{ width: `${band.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
