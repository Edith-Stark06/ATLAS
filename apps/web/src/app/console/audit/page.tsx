import Link from "next/link";
import { ClipboardList, ShieldCheck, ShieldX } from "lucide-react";

import { AuditEvent } from "@/components/audit/audit-event";
import { ApiError, EmptyState } from "@/components/ui/api-error";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelFooter, PanelHeader } from "@/components/ui/panel";
import { StatCard } from "@/components/ui/stat-card";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchLedger, fetchLedgerStats, tryFetch, verifyLedger } from "@/lib/api";
import { auditFacts } from "@/lib/audit";
import { formatDate } from "@/lib/utils";

export const metadata = { title: "Audit — ATLAS" };
export const dynamic = "force-dynamic";

/** A page of history. The ledger itself is the exhaustive record. */
const PAGE_SIZE = 100;

export default async function AuditPage() {
  const [entriesResult, statsResult, verifyResult] = await Promise.all([
    tryFetch(() => fetchLedger({ limit: PAGE_SIZE })),
    tryFetch(fetchLedgerStats),
    tryFetch(verifyLedger),
  ]);

  const header = (
    <PageHeader
      eyebrow="Governance"
      title="Audit"
      description="What happened, who caused it, when, and on what grounds — read back from the same hash-chained records an auditor would recompute."
    />
  );

  if (!entriesResult.ok) {
    return (
      <>
        {header}
        <ApiError error={entriesResult.error} />
      </>
    );
  }

  const entries = entriesResult.data;
  const stats = statsResult.ok ? statsResult.data : null;
  const verification = verifyResult.ok ? verifyResult.data : null;

  // Actors are read out of the pinned payload, so this count reflects what was
  // hashed at the time rather than the current user table.
  const actors = new Set(entries.map((entry) => auditFacts(entry).who));

  return (
    <>
      {header}

      <div className="mb-4 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <StatCard
          label="Events recorded"
          value={(stats?.entries ?? entries.length).toLocaleString("en-US")}
          icon={ClipboardList}
          hint={entries.length < (stats?.entries ?? 0) ? `showing ${entries.length}` : undefined}
        />
        <StatCard
          label="Chain integrity"
          value={verification ? (verification.valid ? "Verified" : "Broken") : "Unknown"}
          icon={verification?.valid ? ShieldCheck : ShieldX}
          tone={verification ? (verification.valid ? "tertiary" : "error") : "primary"}
          hint={
            verification ? `${verification.entriesChecked} checked` : "verification unavailable"
          }
        />
        <StatCard label="Distinct actors" value={String(actors.size)} />
        <StatCard
          label="First record"
          value={stats?.firstRecordedAt ? formatDate(stats.firstRecordedAt) : "—"}
          hint={stats?.lastRecordedAt ? `to ${formatDate(stats.lastRecordedAt)}` : undefined}
        />
      </div>

      <Panel>
        <PanelHeader
          title="Timeline"
          description="Newest first. Expand an event for the grounds it was decided on and the evidence that was hashed."
          action={
            verification ? (
              <StatusChip tone={verification.valid ? "success" : "danger"}>
                {verification.valid ? "Chain verified" : `${verification.breaks.length} breaks`}
              </StatusChip>
            ) : undefined
          }
        />

        {entries.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="Nothing to audit yet"
            description="Events appear here as actions are committed through the pipeline. Seeded history predates the ledger and is therefore not auditable — which is the point of recording it this way."
            action={
              <Link
                href="/console/decisions"
                className="text-body-sm text-primary hover:underline"
              >
                Commit an action →
              </Link>
            }
          />
        ) : (
          <ol className="px-4 py-2">
            {entries.map((entry) => (
              <AuditEvent key={entry.seq} entry={entry} />
            ))}
          </ol>
        )}

        <PanelFooter>
          Editing any recorded field invalidates that entry&apos;s hash and every hash after
          it, so tampering is <span className="text-on-surface">detectable</span> — not
          impossible. Anyone with database access can still change a row; they cannot make it
          verify.{" "}
          <Link href="/console/ledger" className="text-primary hover:underline">
            Open the ledger
          </Link>
          .
        </PanelFooter>
      </Panel>
    </>
  );
}
