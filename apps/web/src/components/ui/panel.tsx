import { cn } from "@/lib/utils";

/**
 * The console's one surface primitive: a flat graphite plane with a hairline
 * border. Separation comes from the step in background value, not from blur,
 * glow or a drop shadow — which is what keeps a dense screen readable.
 */
export function Panel({
  className,
  children,
  /** Staggers the entrance, in ms. Kept short; this is orientation, not flair. */
  delay,
  /** Set false for panels that should not react to the cursor. */
  interactive = false,
  as: Tag = "section",
}: {
  className?: string;
  children: React.ReactNode;
  delay?: number;
  interactive?: boolean;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag
      className={cn(
        "surface-card animate-fade-in-up overflow-hidden",
        interactive && "glass-panel-hover",
        className,
      )}
      style={delay ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}

/**
 * A panel's title row. The icon is muted by default — an accent on every
 * header would spend the brand colour on chrome.
 */
export function PanelHeader({
  title,
  description,
  icon: Icon,
  action,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b border-outline-variant px-4 py-3",
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-headline-sm text-on-surface">
          {Icon && <Icon className="size-4 shrink-0 text-outline" strokeWidth={1.75} />}
          <span className="min-w-0">{title}</span>
        </h2>
        {description && (
          <p className="mt-1 max-w-[75ch] text-body-sm text-on-surface-variant">
            {description}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

/** Body padding that matches PanelHeader's rhythm. */
export function PanelBody({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={cn("px-4 py-3.5", className)}>{children}</div>;
}

/** A quiet closing note under a panel's content. */
export function PanelFooter({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <footer
      className={cn(
        "border-t border-outline-variant px-4 py-2.5 text-body-sm text-on-surface-variant",
        className,
      )}
    >
      {children}
    </footer>
  );
}

const BUTTON_BASE =
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md px-2.5 py-1.5 text-body-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  // The one filled control on a screen — reserve it for the action the page
  // exists to perform.
  primary: "bg-primary text-on-primary hover:bg-primary-bright",
  secondary:
    "border border-outline-strong bg-surface-container-high text-on-surface hover:border-outline hover:bg-surface-container-highest",
  ghost:
    "border border-outline-variant text-on-surface-variant hover:border-outline-strong hover:text-on-surface",
  danger: "border border-error/40 text-error hover:bg-error/10",
};

export function Button({
  children,
  className,
  variant = "secondary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      type="button"
      className={cn(BUTTON_BASE, BUTTON_VARIANTS[variant], className)}
      {...props}
    >
      {children}
    </button>
  );
}

/**
 * Kept under its original name — a dozen call sites use it — but it is now the
 * system's secondary button rather than a violet-tinted one.
 */
export function GhostButton({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(BUTTON_BASE, BUTTON_VARIANTS.secondary, className)}
      {...props}
    >
      {children}
    </button>
  );
}
