import { cn } from "@/lib/utils";

/**
 * Every console page opens the same way: a kicker naming the area, the title,
 * one line of orientation, and the page's actions on the right.
 *
 * `highlight` is kept in the signature because every existing page passes it,
 * but it no longer paints half the title violet — the accent is spent on
 * state and navigation, not on decorating headings. It renders as the second
 * half of the title in the same colour.
 */
export function PageHeader({
  title,
  highlight,
  description,
  eyebrow,
  action,
  className,
}: {
  title: string;
  highlight?: string;
  description?: React.ReactNode;
  /** Small uppercase kicker above the title. */
  eyebrow?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h1 className="text-headline-lg text-on-surface">
          {title}
          {highlight && <span className="text-on-surface"> {highlight}</span>}
        </h1>
        {description && (
          <p className="mt-1.5 max-w-[80ch] text-body-md text-on-surface-variant">
            {description}
          </p>
        )}
      </div>
      {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
    </div>
  );
}

/** A heading between panels, for pages that need more than one band. */
export function SectionHeader({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-2.5 flex flex-wrap items-end justify-between gap-3", className)}>
      <div className="min-w-0">
        <h2 className="text-headline-md text-on-surface">{title}</h2>
        {description && (
          <p className="mt-0.5 text-body-sm text-on-surface-variant">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
