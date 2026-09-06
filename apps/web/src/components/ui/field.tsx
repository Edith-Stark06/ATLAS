import { cn } from "@/lib/utils";

/**
 * The console's input surface: a raised graphite well with a hairline border,
 * turning violet on focus. Shared so every form in the app — rule builder,
 * scenario workspace, capacity planner, execute panel, sign-in — reads as one
 * control set rather than five.
 */
export const FIELD_CLASS =
  "rounded-md border border-outline-variant bg-surface-container-high px-2.5 py-1.5 text-body-sm text-on-surface placeholder:text-outline transition-colors focus:border-primary/60 focus:outline-none disabled:opacity-50";

/** Identifiers, thresholds and versions are typed in monospace. */
export const FIELD_MONO_CLASS = cn(FIELD_CLASS, "font-mono");

/**
 * The same control stretched to its container, for a field that owns a grid
 * cell. Inline controls must NOT use it: a full-width select in the rule
 * builder breaks a condition row that is meant to read as one sentence.
 */
export const FIELD_BLOCK_CLASS = cn(FIELD_CLASS, "w-full");
export const FIELD_MONO_BLOCK_CLASS = cn(FIELD_MONO_CLASS, "w-full");

/** The label above a field. */
export function FieldLabel({
  children,
  hint,
  className,
}: {
  children: React.ReactNode;
  hint?: React.ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("flex items-baseline justify-between gap-2", className)}>
      <span className="eyebrow">{children}</span>
      {hint && <span className="text-label-mono-xs text-outline">{hint}</span>}
    </span>
  );
}
