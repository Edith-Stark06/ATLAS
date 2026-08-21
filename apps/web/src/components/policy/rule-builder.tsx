"use client";

import { useState, useTransition } from "react";
import { FlaskConical, Plus, Trash2, TriangleAlert } from "lucide-react";

import { GhostButton, Panel, PanelHeader } from "@/components/ui/panel";
import { StatusChip } from "@/components/ui/status-chip";
import { simulatePolicyRule } from "@/lib/api";
import type {
  PolicyRule,
  RuleCondition,
  RuleEffect,
  RuleOperator,
  RuleVocabulary,
  SimulateRuleResponse,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const OPERATOR_LABELS: Record<RuleOperator, string> = {
  lt: "<",
  lte: "≤",
  gt: ">",
  gte: "≥",
  eq: "is",
  neq: "is not",
  in: "in",
  not_in: "not in",
};

const EFFECT_LABELS: Record<RuleEffect, string> = {
  allow: "Allow",
  require_human_review: "Require Human Review",
  block: "Block",
};

const MEMBERSHIP_OPERATORS: RuleOperator[] = ["in", "not_in"];
const NUMERIC_OPERATORS: RuleOperator[] = ["lt", "lte", "gt", "gte"];

const SELECT_CLASS =
  "rounded border border-white/10 bg-surface-container-high px-2 py-1.5 font-mono text-body-sm text-on-surface focus:border-secondary focus:outline-none";

/** Operators a given field can legally take — mirrors the engine's
 * parse_condition validation so the UI cannot compose a rule the API will
 * reject (text fields have no ordering). */
function allowedOperators(kind: string, operators: RuleOperator[]): RuleOperator[] {
  if (kind === "str") {
    return operators.filter((o) => !NUMERIC_OPERATORS.includes(o));
  }
  return operators;
}

function parseValue(raw: string, kind: string, operator: RuleOperator): RuleCondition["value"] {
  if (MEMBERSHIP_OPERATORS.includes(operator)) {
    return raw
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
  }
  if (kind === "str") return raw;
  const numeric = Number(raw);
  return Number.isFinite(numeric) ? numeric : raw;
}

function valueToInput(value: RuleCondition["value"]): string {
  return Array.isArray(value) ? value.join(", ") : String(value);
}

export function RuleBuilder({
  vocabulary,
  initialRule,
}: {
  vocabulary: RuleVocabulary;
  initialRule: PolicyRule | null;
}) {
  const [rule, setRule] = useState<PolicyRule>(
    initialRule ?? {
      conditions: [{ field: vocabulary.fields[0]?.key ?? "trust_score", operator: "lt", value: 70 }],
      combinator: "all",
      effect: "require_human_review",
      applies_to: [],
    },
  );
  const [simulation, setSimulation] = useState<SimulateRuleResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const fieldByKey = new Map(vocabulary.fields.map((f) => [f.key, f]));

  function updateCondition(index: number, patch: Partial<RuleCondition>) {
    setRule((current) => ({
      ...current,
      conditions: current.conditions.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    }));
    setSimulation(null);
  }

  function addCondition() {
    setRule((current) => ({
      ...current,
      conditions: [
        ...current.conditions,
        { field: vocabulary.fields[0]?.key ?? "trust_score", operator: "lt", value: 0 },
      ],
    }));
    setSimulation(null);
  }

  function removeCondition(index: number) {
    setRule((current) => ({
      ...current,
      conditions: current.conditions.filter((_, i) => i !== index),
    }));
    setSimulation(null);
  }

  function runSimulation() {
    setError(null);
    startTransition(async () => {
      try {
        setSimulation(await simulatePolicyRule(rule));
      } catch (err) {
        setSimulation(null);
        setError(err instanceof Error ? err.message : String(err));
      }
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <Panel>
        <PanelHeader
          title="Rule Builder"
          description="Compose a rule, then simulate it against recorded decisions before it governs anything."
          action={
            <GhostButton
              onClick={runSimulation}
              disabled={isPending || rule.conditions.length === 0}
              className="flex items-center gap-2 disabled:opacity-50"
            >
              <FlaskConical className="size-3.5" />
              {isPending ? "Simulating…" : "Simulate"}
            </GhostButton>
          }
        />

        <div className="flex flex-col gap-3 p-6">
          {rule.conditions.map((condition, index) => {
            const spec = fieldByKey.get(condition.field);
            const kind = spec?.kind ?? "int";
            const operators = allowedOperators(kind, vocabulary.operators);

            return (
              <div key={index} className="flex flex-wrap items-center gap-2">
                <span className="w-12 shrink-0 font-mono text-label-mono uppercase text-primary">
                  {index === 0 ? "If" : rule.combinator === "all" ? "And" : "Or"}
                </span>

                <select
                  aria-label="Field"
                  className={SELECT_CLASS}
                  value={condition.field}
                  onChange={(e) => {
                    const nextSpec = fieldByKey.get(e.target.value);
                    const nextOperators = allowedOperators(
                      nextSpec?.kind ?? "int",
                      vocabulary.operators,
                    );
                    // Switching to a text field can invalidate the current
                    // operator; fall back to the first legal one.
                    const operator = nextOperators.includes(condition.operator)
                      ? condition.operator
                      : nextOperators[0];
                    updateCondition(index, { field: e.target.value, operator });
                  }}
                >
                  {vocabulary.fields.map((f) => (
                    <option key={f.key} value={f.key}>
                      {f.label}
                    </option>
                  ))}
                </select>

                <select
                  aria-label="Operator"
                  className={SELECT_CLASS}
                  value={condition.operator}
                  onChange={(e) =>
                    updateCondition(index, { operator: e.target.value as RuleOperator })
                  }
                >
                  {operators.map((o) => (
                    <option key={o} value={o}>
                      {OPERATOR_LABELS[o]}
                    </option>
                  ))}
                </select>

                <input
                  aria-label="Value"
                  className={cn(SELECT_CLASS, "w-40")}
                  value={valueToInput(condition.value)}
                  placeholder={
                    MEMBERSHIP_OPERATORS.includes(condition.operator) ? "a, b, c" : "value"
                  }
                  onChange={(e) =>
                    updateCondition(index, {
                      value: parseValue(e.target.value, kind, condition.operator),
                    })
                  }
                />

                {rule.conditions.length > 1 && (
                  <button
                    type="button"
                    aria-label={`Remove condition ${index + 1}`}
                    onClick={() => removeCondition(index)}
                    className="rounded p-1.5 text-outline transition-colors hover:text-error"
                  >
                    <Trash2 className="size-4" />
                  </button>
                )}
              </div>
            );
          })}

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button
              type="button"
              onClick={addCondition}
              className="flex items-center gap-1.5 font-mono text-label-mono text-secondary transition-colors hover:text-primary"
            >
              <Plus className="size-3.5" />
              Add condition
            </button>

            {rule.conditions.length > 1 && (
              <select
                aria-label="Combinator"
                className={SELECT_CLASS}
                value={rule.combinator}
                onChange={(e) => {
                  setRule((c) => ({ ...c, combinator: e.target.value as "all" | "any" }));
                  setSimulation(null);
                }}
                        >
                {vocabulary.combinators.map((c) => (
                  <option key={c} value={c}>
                    {c === "all" ? "match ALL conditions" : "match ANY condition"}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-white/5 pt-4">
            <span className="w-12 shrink-0 font-mono text-label-mono uppercase text-primary">
              Then
            </span>
            <select
              aria-label="Effect"
              className={SELECT_CLASS}
              value={rule.effect}
              onChange={(e) => {
                setRule((c) => ({ ...c, effect: e.target.value as RuleEffect }));
                setSimulation(null);
              }}
            >
              {vocabulary.effects.map((e) => (
                <option key={e} value={e}>
                  {EFFECT_LABELS[e]}
                </option>
              ))}
            </select>

            <span className="ml-2 font-mono text-label-mono uppercase text-on-surface-variant">
              for
            </span>
            <select
              aria-label="Applies to"
              className={SELECT_CLASS}
              value={rule.applies_to[0] ?? ""}
              onChange={(e) => {
                setRule((c) => ({
                  ...c,
                  applies_to: e.target.value ? [e.target.value] : [],
                }));
                setSimulation(null);
              }}
            >
              <option value="">all agents</option>
              {vocabulary.capabilities.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          {error && (
            <p className="mt-2 flex items-start gap-2 rounded border-l-2 border-error bg-error/5 px-4 py-3 text-body-sm text-error">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" />
              {error}
            </p>
          )}
        </div>
      </Panel>

      {simulation && <SimulationResult simulation={simulation} />}
    </div>
  );
}

function DecisionRow({
  decision,
  showSimulated,
}: {
  decision: SimulateRuleResponse["sample"][number];
  showSimulated: boolean;
}) {
  return (
    <li className="flex flex-wrap items-center gap-3 px-6 py-3">
      <span className="font-mono text-body-sm text-on-surface">{decision.decisionId}</span>
      <span className="min-w-0 flex-1 truncate text-body-sm text-on-surface-variant">
        {decision.action}
      </span>
      <span className="font-mono text-status-label uppercase text-outline">
        was {decision.recordedOutcome}
      </span>
      {showSimulated && (
        <>
          <span className="text-outline">→</span>
          <StatusChip
            tone={
              decision.simulatedOutcome === "blocked"
                ? "danger"
                : decision.simulatedOutcome === "escalated"
                  ? "warning"
                  : "success"
            }
          >
            {decision.simulatedOutcome}
          </StatusChip>
        </>
      )}
    </li>
  );
}

function SimulationResult({ simulation }: { simulation: SimulateRuleResponse }) {
  const { evaluated, matched, wouldBlock, wouldEscalate, sample } = simulation;

  // This rule is simulated *alone*, so a decision it does not match falls
  // through to "allow" — which is not the same as the rule releasing it, as
  // other active policies may still restrict it. Splitting the results this
  // way avoids implying a coverage gap is an outcome reversal.
  const caught = sample.filter((s) => s.matched);
  const missedRestrictions = sample.filter(
    (s) => !s.matched && s.recordedOutcome !== "approved",
  );

  return (
    <Panel>
      <PanelHeader
        title="Simulation Result"
        description={`This rule alone, replayed against ${evaluated} recorded decision${evaluated === 1 ? "" : "s"}. Nothing was written.`}
        action={
          <StatusChip tone={matched > 0 ? "info" : "neutral"}>
            catches {matched} of {evaluated}
          </StatusChip>
        }
      />

      <dl className="grid grid-cols-3 divide-white/5 md:divide-x">
        {[
          { label: "Catches", value: matched, tone: "text-on-surface" },
          { label: "Would block", value: wouldBlock, tone: "text-error" },
          { label: "Would escalate", value: wouldEscalate, tone: "text-brand-amber" },
        ].map((stat) => (
          <div key={stat.label} className="px-6 py-4">
            <dt className="font-mono text-status-label uppercase text-on-surface-variant">
              {stat.label}
            </dt>
            <dd className={cn("mt-1 font-mono text-headline-sm", stat.tone)}>{stat.value}</dd>
          </div>
        ))}
      </dl>

      {caught.length > 0 && (
        <div className="border-t border-white/5">
          <p className="px-6 py-3 font-mono text-label-mono uppercase text-on-surface-variant">
            Decisions this rule catches
          </p>
          <ul className="divide-y divide-white/5">
            {caught.map((decision) => (
              <DecisionRow key={decision.decisionId} decision={decision} showSimulated />
            ))}
          </ul>
        </div>
      )}

      {missedRestrictions.length > 0 && (
        <div className="border-t border-white/5">
          <p className="px-6 py-3 font-mono text-label-mono uppercase text-on-surface-variant">
            Restricted decisions this rule would not catch
          </p>
          <ul className="divide-y divide-white/5">
            {missedRestrictions.map((decision) => (
              <DecisionRow
                key={decision.decisionId}
                decision={decision}
                showSimulated={false}
              />
            ))}
          </ul>
          <p className="border-t border-white/5 px-6 py-3 text-status-label text-outline">
            These were escalated or blocked by other policies. This rule on its own does not
            reach them — that is a coverage gap, not an outcome reversal.
          </p>
        </div>
      )}

      {matched === 0 && missedRestrictions.length === 0 && (
        <p className="border-t border-white/5 px-6 py-4 text-body-sm text-on-surface-variant">
          This rule matches none of the recorded decisions.
        </p>
      )}
    </Panel>
  );
}
