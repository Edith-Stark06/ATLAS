import { cn } from "@/lib/utils";

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <section className={cn("glass-panel rounded-xl", className)}>{children}</section>;
}

export function PanelHeader({
  title,
  description,
  icon: Icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "flex items-start justify-between gap-4 border-b border-white/5 px-6 py-4",
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-headline-sm text-on-surface">
          {Icon && <Icon className="size-5 shrink-0 text-secondary" />}
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-body-sm text-on-surface-variant">{description}</p>
        )}
      </div>
      {action}
    </header>
  );
}

export function GhostButton({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "shrink-0 rounded border border-primary/30 bg-primary/5 px-3 py-1.5 font-mono text-label-mono text-primary transition-colors hover:bg-primary/10",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
