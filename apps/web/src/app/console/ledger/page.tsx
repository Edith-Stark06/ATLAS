import { CircleCheck, Cpu, ScrollText, ShieldAlert, TriangleAlert } from "lucide-react";

import { LedgerEntryRow } from "@/components/ledger/ledger-entry-row";
import { ApiError } from "@/components/ui/api-error";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchLedger, fetchLedgerStats, tryFetch, verifyLedger } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

export const metadata = { title: "Governance Ledger — ATLAS" };
export const dynamic = "force-dynamic";

const KIND_LABELS: Record<string, string> = {
  decision_recorded: "Decisions",
  policy_activated: "Policy changes",
  trust_recomputed: "Trust recomputes",
};

export default async function LedgerPage() {
  const [entriesResult, statsResult, verifyResult] = await Promise.all([
    tryFetch(() => fetchLedger({ limit: 100 })),
    tryFetch(fetchLedgerStats),
    tryFetch(verifyLedger),
  ]);

  if (!entriesResult.ok) {
    return (
      <>
        <PageHeader
          title="Governance"
          highlight="Ledger"
          description="An append-only record of every decision, the rule versions it was judged against, and the model that scored it."
        />
        <ApiError error={entriesResult.error} />
      </>
    );
  }

  const entries = entriesResult.data;
  const stats = statsResult.ok ? statsResult.data : null;
  const verification = verifyResult.ok ? verifyResult.data : null;
  const valid = verification?.valid ?? false;

  return (
    <>
      <PageHeader
        title="Governance"
        highlight="Ledger"
        description="An append-only record of every decision, the rule versions it was judged against, and the model that scored it."
      />

      <Panel className="mb-stack-md" interactive={false}>
        <PanelHeader
          title="Chain integrity"
          icon={valid ? CircleCheck : ShieldAlert}
          description={
            verification
              ? "Every hash recomputed and every link checked on this request — not a stored flag."
              : "Verification could not be reached."
          }
          action={
            verification ? (
              <StatusChip tone={valid ? "success" : "danger"}>
                {valid ? "Verified" : `${verification.breaks.length} breaks`}
              </StatusChip>
            ) : undefined
          }
        />

        <dl className="grid grid-cols-2 divide-white/5 md:grid-cols-4 md:divide-x">
          <div className="px-6 py-4">
            <dt className="font-mono text-status-label uppercase text-on-surface-variant">
              Entries
            </dt>
            <dd className="mt-1 font-mono text-body-md text-on-surface">
              {verification?.entriesChecked ?? stats?.entries ?? "—"}
            </dd>
          </div>
          <div className="px-6 py-4">
            <dt className="font-mono text-status-label uppercase text-on-surface-variant">
              Head
            </dt>
            <dd className="mt-1 font-mono text-body-md text-on-surface">
              {stats?.headSeq !== null && stats?.headSeq !== undefined ? `#${stats.headSeq}` : "—"}
            </dd>
          </div>
          <div className="px-6 py-4">
            <dt className="font-mono text-status-label uppercase text-on-surface-variant">
              First record
            </dt>
            <dd className="mt-1 font-mono text-body-md text-on-surface">
              {stats?.firstRecordedAt ? formatDate(stats.firstRecordedAt) : "—"}
            </dd>
          </div>
          <div className="px-6 py-4">
            <dt className="flex items-center gap-1.5 font-mono text-status-label uppercase text-on-surface-variant">
              <Cpu className="size-3" /> Model
            </dt>
            <dd className="mt-1 font-mono text-body-md text-on-surface">
              {stats?.modelFingerprint ? stats.modelFingerprint.slice(0, 12) : "none"}
            </dd>
          </div>
        </dl>

        {verification && (
          <div className="border-t border-white/5 px-6 py-4">
            <p className="font-mono text-status-label uppercase text-on-surface-variant">
              Head hash
            </p>
            <p
              className={cn(
                "mt-1 break-all font-mono text-body-sm",
                valid ? "text-tertiary" : "text-error",
              )}
            >
              {verification.headHash ?? "empty chain"}
            </p>
            <p className="mt-3 text-body-sm text-on-surface-variant">
              Editing any recorded field invalidates that entry&apos;s hash and every hash after
              it. This makes tampering <span className="text-on-surface">detectable</span>, not
              impossible — anyone with database access can still change a row, but they cannot
              make it verify.
            </p>
          </div>
        )}

        {verification && !valid && (
          <ul className="border-t border-white/5">
            {verification.breaks.map((chainBreak, i) => (
              <li
                key={`${chainBreak.seq}-${i}`}
                className="flex items-start gap-2.5 border-b border-white/5 px-6 py-3 last:border-b-0"
              >
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-error" />
                <div className="min-w-0">
                  <p className="text-body-sm text-error">
                    Entry #{chainBreak.seq} — {chainBreak.reason}
                  </p>
                  <p className="mt-1 break-all font-mono text-status-label text-on-surface-variant">
                    expected {chainBreak.expected} · found {chainBreak.found}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {stats && Object.keys(stats.countsByKind).length > 0 && (
        <div className="mb-stack-md grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Object.entries(stats.countsByKind).map(([kind, count]) => (
            <Panel key={kind} className="px-6 py-4" interactive={false}>
              <p className="font-mono text-status-label uppercase text-on-surface-variant">
                {KIND_LABELS[kind] ?? kind}
              </p>
              <p className="mt-1 text-headline-md text-on-surface">{count}</p>
            </Panel>
          ))}
        </div>
      )}

      <Panel interactive={false}>
        <PanelHeader
          title="Records"
          icon={ScrollText}
          description={
            entries.length === 0
              ? "Nothing recorded yet — decisions appear here as they are committed."
              : "Newest first. Expand an entry to see the evidence that was hashed."
          }
        />
        <ul>
          {entries.map((entry) => (
            <LedgerEntryRow key={entry.seq} entry={entry} />
          ))}
        </ul>
      </Panel>
    </>
  );
}
