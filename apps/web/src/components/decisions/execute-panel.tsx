"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState, useTransition } from "react";
import { CircleCheck, CircleSlash, Play, TriangleAlert } from "lucide-react";

import { OutcomeBadge } from "@/components/ui/outcome-badge";
import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { executeDecision } from "@/lib/api-client";
import type { Agent, ExecuteDecisionResponse } from "@/lib/types";
import { formatUsd } from "@/lib/utils";

const FIELD_CLASS =
  "rounded border border-white/10 bg-surface-container-high px-2 py-1.5 font-mono text-body-sm text-on-surface focus:border-secondary focus:outline-none";

export function ExecutePanel({ agents }: { agents: Agent[] }) {
  const router = useRouter();
  const [agentId, setAgentId] = useState(agents[0]?.id ?? "");
  const [action, setAction] = useState("Approve vendor payment");
  const [amount, setAmount] = useState("1200");
  const [risk, setRisk] = useState(35);
  const [result, setResult] = useState<ExecuteDecisionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function run() {
    startTransition(async () => {
      setError(null);
      try {
        const trimmed = amount.trim();
        const committed = await executeDecision({
          agentId,
          action: action.trim() || "Proposed action",
          amountUsd: trimmed === "" ? null : Number(trimmed),
          riskScore: risk,
        });
        setResult(committed);
        // The decision list and ledger above are server-rendered; without this
        // the page would keep showing a table that no longer matches reality.
        router.refresh();
      } catch (err) {
        setResult(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <Panel className="mb-stack-md" interactive={false}>
      <PanelHeader
        title="Execute an action"
        icon={Play}
        description="Commits for real: writes a decision, its policy checks, and an append-only ledger entry. For a what-if, use the Simulation Engine."
      />

      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-4">
        <label className="flex flex-col gap-1.5">
          <span className="font-mono text-status-label uppercase text-on-surface-variant">
            Agent
          </span>
          <select
            className={FIELD_CLASS}
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
          >
            {agents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5 md:col-span-2">
          <span className="font-mono text-status-label uppercase text-on-surface-variant">
            Action
          </span>
          <input
            className={FIELD_CLASS}
            value={action}
            maxLength={300}
            onChange={(e) => setAction(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="font-mono text-status-label uppercase text-on-surface-variant">
            Amount (USD)
          </span>
          <input
            className={FIELD_CLASS}
            inputMode="decimal"
            value={amount}
            placeholder="none"
            onChange={(e) => setAmount(e.target.value)}
          />
        </label>

        <label className="flex flex-col gap-1.5 md:col-span-3">
          <span className="font-mono text-status-label uppercase text-on-surface-variant">
            Risk score — {risk}
          </span>
          <input
            type="range"
            min={0}
            max={100}
            className="accent-primary"
            value={risk}
            onChange={(e) => setRisk(Number(e.target.value))}
          />
        </label>

        <GhostButton
          className="flex items-center justify-center gap-2 self-end py-2"
          onClick={run}
          disabled={pending}
        >
          <Play className="size-3.5" />
          {pending ? "Deciding…" : "Execute"}
        </GhostButton>
      </div>

      {error && (
        <p className="mx-6 mb-6 flex items-start gap-2 rounded border-l-2 border-error bg-error/5 px-4 py-3 text-body-sm text-error">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}

      {result && (
        <div className="border-t border-white/5 px-6 py-4">
          <div className="mb-3 flex flex-wrap items-center gap-3">
            {result.executed ? (
              <CircleCheck className="size-4 text-tertiary" />
            ) : (
              <CircleSlash className="size-4 text-error" />
            )}
            <span className="font-mono text-body-sm text-on-surface">{result.decisionId}</span>
            <OutcomeBadge outcome={result.outcome} />
            <span className="font-mono text-status-label text-outline">
              {result.confidence}% · {result.latencyMs}ms
            </span>
            <Link
              href="/console/ledger"
              className="ml-auto font-mono text-status-label uppercase text-primary hover:underline"
            >
              Ledger #{result.ledgerSeq} →
            </Link>
          </div>

          <p className="mb-2 text-body-sm text-on-surface-variant">{result.rationale}</p>

          <p className="text-body-sm text-on-surface-variant">
            {result.executed ? (
              <>
                Cleared to run —{" "}
                <span className="font-mono text-on-surface">
                  {formatUsd(result.expectedExposureUsd)}
                </span>{" "}
                moves.
              </>
            ) : (
              <>
                Not cleared to run —{" "}
                <span className="font-mono text-brand-amber">
                  {formatUsd(result.withheldUsd)}
                </span>{" "}
                held back.
              </>
            )}
          </p>
        </div>
      )}
    </Panel>
  );
}
