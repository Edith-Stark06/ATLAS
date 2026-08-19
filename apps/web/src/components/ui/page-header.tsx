export function PageHeader({
  title,
  highlight,
  description,
  action,
}: {
  title: string;
  /** Rendered in the primary accent colour, immediately after `title`. */
  highlight?: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-stack-lg flex items-start justify-between gap-6">
      <div>
        <h1 className="mb-2 text-headline-lg text-on-surface">
          {title} {highlight && <span className="text-primary">{highlight}</span>}
        </h1>
        {description && (
          <p className="max-w-3xl text-body-lg text-on-surface-variant">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}
