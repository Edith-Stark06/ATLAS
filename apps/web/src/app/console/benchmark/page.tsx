import Link from "next/link";
import { Crown, GitCompareArrows, Medal, TrendingDown, TrendingUp, TriangleAlert } from "lucide-react";

import { ApiError } from "@/components/ui/api-error";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { fetchCohortBenchmark, fetchCohorts, fetchScoreChanges, tryFetch } from "@/lib/api";
import type { BenchmarkAgentScore, BenchmarkCriterion } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata = { title: "Agent Benchmark — ATLAS" };
export const dynamic = "force-dynamic";

const CRITERION_ORDER = ["security", "compliance", "efficiency", "reliability", "speed"];

function scoreTone(score: number): string {
  if (score >= 90) return "text-tertiary";
  if (score >= 75) return "text-on-surface";
  if (score >= 50) return "text-brand-amber";
  return "text-error";
}

function barTone(score: number): string {
  if (score >= 90) return "bg-tertiary";
  if (score >= 75) return "bg-secondary";
  if (score >= 50) return "bg-brand-amber";
  return "bg-error";
}

function CriterionCell({ criterion }: { criterion: BenchmarkCriterion }) {
  return (
    <td className="px-3 py-3" title={criterion.basis}>
      <div className="flex items-center gap-2">
        <div className="h-1 w-10 shrink-0 overflow-hidden rounded-full bg-surface-container-highest">
          <span
            className={cn("block h-full rounded-full", barTone(criterion.score))}
            style={{ width: `${criterion.score}%` }}
          />
        </div>
        <span className={cn("font-mono text-body-sm tabular-nums", scoreTone(criterion.score))}>
          {criterion.score.toFixed(0)}
        </span>
      </div>
    </td>
  );
}

function AgentRow({
  agent,
  rank,
  isLeader,
  gaps,
}: {
  agent: BenchmarkAgentScore;
  rank: number;
  isLeader: boolean;
  gaps: { label: string; compositeCost: number }[];
}) {
  const ordered = CRITERION_ORDER.map(
    (key) => agent.criteria.find((c) => c.key === key),
  ).filter((c): c is BenchmarkCriterion => Boolean(c));

  return (
    <tr className={cn("border-b border-white/5 last:border-b-0", isLeader && "bg-tertiary/5")}>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          {isLeader ? (
            <Crown className="size-3.5 text-tertiary" />
          ) : (
            <span className="w-3.5 text-center font-mono text-status-label text-outline">
              {rank}
            </span>
          )}
        </div>
      </td>

      <td className="px-3 py-3">
        <Link
          href={`/console/agents/${encodeURIComponent(agent.agentId)}`}
          className="text-body-sm text-on-surface hover:text-primary"
        >
          {agent.agentName}
        </Link>
        <div className="mt-0.5 flex items-center gap-2">
          <span className="font-mono text-status-label text-outline">
            {agent.decisions.toLocaleString()} decision{agent.decisions === 1 ? "" : "s"}
          </span>
          {agent.thinEvidence && (
            <span className="flex items-center gap-1 font-mono text-status-label uppercase text-brand-amber">
              <TriangleAlert className="size-3" />
              thin evidence
            </span>
          )}
        </div>
      </td>

      <td className="px-3 py-3">
        <span className={cn("font-mono text-body-md tabular-nums", scoreTone(agent.composite))}>
          {agent.composite.toFixed(1)}
        </span>
      </td>

      {ordered.map((criterion) => (
        <CriterionCell key={criterion.key} criterion={criterion} />
      ))}

      <td className="px-4 py-3">
        {isLeader ? (
          <span className="font-mono text-status-label uppercase text-tertiary">benchmark</span>
        ) : gaps.length > 0 ? (
          <span className="text-body-sm text-on-surface-variant">
            <span className="text-brand-amber">−{gaps[0].compositeCost.toFixed(1)}</span>{" "}
            {gaps[0].label.toLowerCase()}
          </span>
        ) : (
          <span className="font-mono text-status-label text-outline">—</span>
        )}
      </td>
    </tr>
  );
}

export default async function BenchmarkPage({
  searchParams,
}: {
  searchParams: Promise<{ cohort?: string; agent?: string }>;
}) {
  const params = await searchParams;
  const cohortsResult = await tryFetch(fetchCohorts);

  const header = (
    <PageHeader
      title="Agent"
      highlight="Benchmark"
      description="Given several agents doing the same job, which one should get more of the work — and what would the others have to change to catch up."
    />
  );

  if (!cohortsResult.ok) {
    return (
      <>
        {header}
        <ApiError error={cohortsResult.error} />
      </>
    );
  }

  const cohorts = cohortsResult.data;
  if (cohorts.length === 0) {
    return (
      <>
        {header}
        <ApiError error="No agents registered." />
      </>
    );
  }

  const selected = params.cohort ?? cohorts[0].capability;
  const [benchmarkResult, changesResult] = await Promise.all([
    tryFetch(() => fetchCohortBenchmark(selected, 30)),
    params.agent ? tryFetch(() => fetchScoreChanges(params.agent!, 60)) : Promise.resolve(null),
  ]);

  return (
    <>
      {header}

      <div className="mb-stack-md flex flex-wrap gap-2">
        {cohorts.map((cohort) => (
          <Link
            key={cohort.capability}
            href={`/console/benchmark?cohort=${encodeURIComponent(cohort.capability)}`}
            className={cn(
              "flex items-center gap-2 rounded border px-3 py-1.5 text-body-sm transition-colors",
              cohort.capability === selected
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-white/10 text-on-surface-variant hover:text-on-surface",
            )}
          >
            {cohort.capability}
            <span className="font-mono text-status-label text-outline">{cohort.agents}</span>
          </Link>
        ))}
      </div>

      {!benchmarkResult.ok ? (
        <ApiError error={benchmarkResult.error} />
      ) : (
        (() => {
          const benchmark = benchmarkResult.data;

          return (
            <>
              <Panel className="mb-stack-md" interactive={false}>
                <PanelHeader
                  title={`${benchmark.capability} — ${benchmark.scored.length} agents`}
                  icon={Medal}
                  description={
                    benchmark.comparable
                      ? `Ranked over ${benchmark.windowDays} days. Scores are absolute, not scaled to the cohort — a strong cohort looks strong rather than manufacturing a worst member at zero.`
                      : "Only one agent does this job, so there is nothing to compare it against."
                  }
                  action={
                    <div className="flex flex-wrap gap-1.5">
                      {CRITERION_ORDER.map((key) => (
                        <span
                          key={key}
                          className="rounded bg-surface-container-highest px-1.5 py-0.5 font-mono text-status-label uppercase text-on-surface-variant"
                          title={`Weight in the composite: ${benchmark.weights[key]}`}
                        >
                          {key.slice(0, 3)} {(benchmark.weights[key] * 100).toFixed(0)}%
                        </span>
                      ))}
                    </div>
                  }
                />

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[56rem] border-collapse">
                    <thead>
                      <tr className="border-b border-white/5">
                        <th className="px-4 py-2 text-left font-mono text-status-label uppercase text-on-surface-variant">
                          #
                        </th>
                        <th className="px-3 py-2 text-left font-mono text-status-label uppercase text-on-surface-variant">
                          Agent
                        </th>
                        <th className="px-3 py-2 text-left font-mono text-status-label uppercase text-on-surface-variant">
                          Score
                        </th>
                        {CRITERION_ORDER.map((key) => (
                          <th
                            key={key}
                            className="px-3 py-2 text-left font-mono text-status-label uppercase text-on-surface-variant"
                          >
                            {key}
                          </th>
                        ))}
                        <th className="px-4 py-2 text-left font-mono text-status-label uppercase text-on-surface-variant">
                          Biggest gap
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {benchmark.scored.map((agent, index) => (
                        <AgentRow
                          key={agent.agentId}
                          agent={agent}
                          rank={index + 1}
                          isLeader={agent.agentId === benchmark.leaderId}
                          gaps={benchmark.gaps[agent.agentId] ?? []}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>

                <p className="border-t border-white/5 px-6 py-3 text-body-sm text-on-surface-variant">
                  An agent without a track record cannot be the benchmark, however well it
                  scores — the leader is what every other agent&apos;s gap is measured against,
                  so one lucky decision must not set the bar. Its real score is still shown.
                </p>
              </Panel>

              {/* --- what would close the gap --- */}
              {benchmark.comparable && (
                <div className="mb-stack-md grid grid-cols-1 gap-4 xl:grid-cols-2">
                  <Panel interactive={false}>
                    <PanelHeader
                      title="Where the cohort loses ground"
                      icon={GitCompareArrows}
                      description="Ranked by what would actually move the composite, not by raw point difference."
                    />
                    <ul className="divide-y divide-white/5">
                      {benchmark.scored
                        .filter((a) => (benchmark.gaps[a.agentId] ?? []).length > 0)
                        .slice(0, 6)
                        .map((agent) => {
                          const gaps = benchmark.gaps[agent.agentId] ?? [];
                          return (
                            <li key={agent.agentId} className="px-6 py-3">
                              <p className="text-body-sm text-on-surface">{agent.agentName}</p>
                              <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                                {gaps.slice(0, 3).map((gap) => (
                                  <span
                                    key={gap.key}
                                    className="text-body-sm text-on-surface-variant"
                                  >
                                    {gap.label}{" "}
                                    <span className="font-mono text-error">
                                      {gap.agentScore.toFixed(0)}
                                    </span>
                                    {" → "}
                                    <span className="font-mono text-tertiary">
                                      {gap.leaderScore.toFixed(0)}
                                    </span>
                                    <span className="ml-1 font-mono text-status-label text-outline">
                                      +{gap.compositeCost.toFixed(1)}
                                    </span>
                                  </span>
                                ))}
                              </div>
                            </li>
                          );
                        })}
                    </ul>
                  </Panel>

                  {/* --- mechanism ranking --- */}
                  <Panel interactive={false}>
                    <PanelHeader
                      title="What moved a score"
                      icon={changesResult?.ok && changesResult.data.delta < 0 ? TrendingDown : TrendingUp}
                      description="Pick an agent to decompose its trust change into the factors that caused it."
                    />

                    <div className="flex flex-wrap gap-1.5 px-6 py-3">
                      {benchmark.scored.slice(0, 8).map((agent) => (
                        <Link
                          key={agent.agentId}
                          href={`/console/benchmark?cohort=${encodeURIComponent(selected)}&agent=${encodeURIComponent(agent.agentId)}`}
                          className={cn(
                            "rounded border px-2 py-1 font-mono text-status-label transition-colors",
                            agent.agentId === params.agent
                              ? "border-primary/40 bg-primary/10 text-primary"
                              : "border-white/10 text-on-surface-variant hover:text-on-surface",
                          )}
                        >
                          {agent.agentId.replace("agt-", "")}
                        </Link>
                      ))}
                    </div>

                    {changesResult === null ? (
                      <p className="border-t border-white/5 px-6 py-4 text-body-sm text-outline">
                        No agent selected.
                      </p>
                    ) : !changesResult.ok ? (
                      <div className="border-t border-white/5 p-4">
                        <ApiError error={changesResult.error} />
                      </div>
                    ) : (
                      (() => {
                        const change = changesResult.data;
                        const moved = change.contributions.filter(
                          (c) => Math.abs(c.contribution) >= 0.005,
                        );

                        return (
                          <div className="border-t border-white/5">
                            <div className="flex flex-wrap items-baseline gap-3 px-6 py-3">
                              <span className="font-mono text-body-md text-on-surface-variant">
                                {change.beforeScore} → {change.afterScore}
                              </span>
                              <span
                                className={cn(
                                  "font-mono text-headline-sm",
                                  change.delta >= 0 ? "text-tertiary" : "text-error",
                                )}
                              >
                                {change.delta > 0 ? "+" : ""}
                                {change.delta}
                              </span>
                              <StatusChip tone={change.reconciles ? "success" : "danger"}>
                                {change.reconciles ? "reconciles" : "does not reconcile"}
                              </StatusChip>
                            </div>

                            <ul className="divide-y divide-white/5">
                              {moved.map((contribution) => (
                                <li
                                  key={contribution.key}
                                  className="flex flex-wrap items-center gap-3 px-6 py-2"
                                >
                                  <span className="min-w-0 flex-1 basis-40 truncate text-body-sm text-on-surface">
                                    {contribution.label}
                                  </span>
                                  <span className="font-mono text-status-label text-outline">
                                    {contribution.before} → {contribution.after}
                                  </span>
                                  <span
                                    className={cn(
                                      "w-16 text-right font-mono text-body-sm",
                                      contribution.contribution >= 0
                                        ? "text-tertiary"
                                        : "text-error",
                                    )}
                                  >
                                    {contribution.contribution > 0 ? "+" : ""}
                                    {contribution.contribution.toFixed(2)}
                                  </span>
                                  {/* A weight change is a different event from
                                      the factor itself moving. */}
                                  {Math.abs(contribution.fromWeight) >= 0.005 && (
                                    <StatusChip tone="warning">re-weighted</StatusChip>
                                  )}
                                </li>
                              ))}
                            </ul>

                            {change.residualShare > 0.05 && (
                              <p className="border-t border-white/5 px-6 py-3 text-body-sm text-on-surface-variant">
                                <span className="font-mono text-brand-amber">
                                  {(change.residualShare * 100).toFixed(0)}%
                                </span>{" "}
                                of this change is not attributable to any factor. The score
                                comes from a trained model rather than the weighted sum this
                                breakdown assumes — so the model judged the agent differently
                                for reasons its inputs do not capture. Reported rather than
                                spread across the factors, which would turn one honest gap into
                                five small fabrications.
                              </p>
                            )}
                          </div>
                        );
                      })()
                    )}
                  </Panel>
                </div>
              )}
            </>
          );
        })()
      )}
    </>
  );
}
