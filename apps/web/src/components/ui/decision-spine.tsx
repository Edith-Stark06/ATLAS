import { cn } from "@/lib/utils";

export type SpineTone = "neutral" | "brand" | "success" | "warning" | "danger";

const RULE_TONE: Record<SpineTone, string> = {
  neutral: "bg-outline-variant",
  brand: "bg-primary/60",
  success: "bg-tertiary/60",
  warning: "bg-brand-amber/60",
  danger: "bg-error/60",
};

const MARKER_TONE: Record<SpineTone, string> = {
  neutral: "border-outline-strong bg-surface-container-high text-outline",
  brand: "border-primary/60 bg-surface-container-high text-primary",
  success: "border-tertiary/50 bg-surface-container-high text-tertiary",
  warning: "border-brand-amber/50 bg-surface-container-high text-brand-amber",
  danger: "border-error/50 bg-surface-container-high text-error",
};

export interface SpineStage {
  key: string;
  /** REQUEST / POLICY / TRUST / DECISION / LEDGER. */
  label: string;
  /** One line answering what this stage concluded. Never a paragraph. */
  verdict?: React.ReactNode;
  tone?: SpineTone;
  /** The stage's evidence. Rendered inside the spine's right-hand column. */
  children?: React.ReactNode;
}

/**
 * The ATLAS Decision Spine.
 *
 * Every decision is the same five steps in the same order, so the investigation
 * view renders them as one continuous vertical structure rather than five
 * unrelated cards. The rule between two markers is the spine; the colour of a
 * segment is the state of the stage above it, which is what lets the eye find
 * where a decision turned.
 *
 * Structural lines and a marker, nothing else — no glow, no animation, no
 * connector art. The technical character comes from the alignment.
 */
export function DecisionSpine({
  stages,
  className,
}: {
  stages: SpineStage[];
  className?: string;
}) {
  return (
    <ol className={cn("flex flex-col", className)}>
      {stages.map((stage, index) => {
        const tone = stage.tone ?? "neutral";
        const isLast = index === stages.length - 1;

        return (
          <li key={stage.key} className="relative flex gap-3 sm:gap-4">
            {/* Rail column: marker plus the segment descending from it. */}
            <div className="flex w-6 shrink-0 flex-col items-center">
              <span
                className={cn(
                  "flex size-6 shrink-0 items-center justify-center rounded-md border font-mono text-label-mono-xs",
                  MARKER_TONE[tone],
                )}
                aria-hidden
              >
                {String(index + 1).padStart(2, "0")}
              </span>
              {!isLast && <span className={cn("w-px flex-1", RULE_TONE[tone])} aria-hidden />}
            </div>

            <div className={cn("min-w-0 flex-1", isLast ? "pb-0" : "pb-6")}>
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <h3 className="eyebrow text-on-surface-variant">{stage.label}</h3>
                {stage.verdict && (
                  <span className="text-body-sm text-on-surface-variant">{stage.verdict}</span>
                )}
              </div>
              {stage.children && <div className="mt-2.5">{stage.children}</div>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * A labelled fact inside a spine stage. Two columns on anything but the
 * narrowest screen, so a stage's evidence scans as a list rather than prose.
 */
export function SpineFacts({
  facts,
  columns = 2,
  className,
}: {
  facts: { label: string; value: React.ReactNode; mono?: boolean }[];
  columns?: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <dl
      className={cn(
        "grid gap-x-5 gap-y-2.5",
        columns === 1 && "grid-cols-1",
        columns === 2 && "grid-cols-1 sm:grid-cols-2",
        columns === 3 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        className,
      )}
    >
      {facts.map((fact) => (
        <div key={fact.label} className="min-w-0">
          <dt className="eyebrow">{fact.label}</dt>
          <dd
            className={cn(
              "mt-1 break-words text-body-md text-on-surface",
              fact.mono && "font-mono text-body-sm",
            )}
          >
            {fact.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
