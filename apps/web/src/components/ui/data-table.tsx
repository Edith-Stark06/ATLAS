import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  /** Right-align numerics so digits line up down the column. */
  align?: "left" | "right";
  /** Hide below a breakpoint on narrow screens rather than squeezing. */
  hideBelow?: "sm" | "md" | "lg" | "xl";
  width?: string;
  cell: (row: T) => React.ReactNode;
}

const HIDE_CLASS: Record<NonNullable<Column<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
};

/**
 * The console's one table.
 *
 * Rows are separated by a hairline rather than by banding, headers are quiet
 * uppercase labels, and the whole thing scrolls inside its own container so a
 * wide table never makes the page scroll sideways.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  /** Turns each row into a link target without nesting an <a> in every cell. */
  onRowHref,
  minWidthClass = "md:min-w-[48rem]",
  /** Fixed layout honours the declared widths; a long cell then truncates
   * instead of shouldering the last columns out of the panel. */
  fixed = false,
  empty,
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowHref?: (row: T) => string;
  /**
   * The width below which the table scrolls sideways, as a *responsive* class
   * rather than an inline style. An unconditional min-width forces a phone to
   * scroll past the identifying column to reach anything else; scoping it to
   * `md:` lets the small-screen layout collapse to the columns that survive
   * `hideBelow` and fit them in the viewport.
   */
  minWidthClass?: string;
  fixed?: boolean;
  empty?: React.ReactNode;
  className?: string;
}) {
  if (rows.length === 0 && empty) {
    return <>{empty}</>;
  }

  return (
    <div className={cn("custom-scrollbar overflow-x-auto", className)}>
      <table className={cn("w-full border-collapse", minWidthClass, fixed && "table-fixed")}>
        <thead>
          <tr className="border-b border-outline-variant">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                style={column.width ? { width: column.width } : undefined}
                className={cn(
                  "eyebrow whitespace-nowrap px-3 py-2 first:pl-4 last:pr-4",
                  column.align === "right" ? "text-right" : "text-left",
                  column.hideBelow && HIDE_CLASS[column.hideBelow],
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-outline-variant">
          {rows.map((row) => {
            const href = onRowHref?.(row);
            return (
              <tr
                key={rowKey(row)}
                className={cn(
                  "transition-colors",
                  href && "cursor-pointer hover:bg-surface-container-high",
                )}
              >
                {columns.map((column, index) => (
                  <td
                    key={column.key}
                    className={cn(
                      "overflow-hidden px-3 py-2.5 align-middle first:pl-4 last:pr-4",
                      column.align === "right" && "text-right",
                      column.hideBelow && HIDE_CLASS[column.hideBelow],
                    )}
                  >
                    {/* One anchor per row, on the identifying cell. A
                        stretched overlay would need `position: relative` on
                        the <tr>, which browsers handle inconsistently; an
                        anchor in every cell would make one row a dozen tab
                        stops. */}
                    {href && index === 0 ? (
                      <a href={href} className="block transition-colors hover:text-primary">
                        {column.cell(row)}
                      </a>
                    ) : (
                      column.cell(row)
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
