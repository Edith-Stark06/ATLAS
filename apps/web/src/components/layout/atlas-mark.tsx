import { cn } from "@/lib/utils";

/**
 * The ATLAS mark: a governed action passing through a gate.
 *
 * Deliberately geometric and drawn from the product's own idea — a request
 * entering, a boundary, a verdict leaving — rather than an abstract glyph or
 * anything with a brain or a spark in it.
 */
export function AtlasMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      className={cn("size-full", className)}
      aria-hidden
    >
      {/* The gate. */}
      <rect
        x="3.5"
        y="3.5"
        width="17"
        height="17"
        rx="4"
        stroke="currentColor"
        strokeOpacity="0.35"
        strokeWidth="1.25"
      />
      {/* The action passing through it, checked at the centre. */}
      <path
        d="M2 12h4.5M17.5 12H22"
        stroke="currentColor"
        strokeOpacity="0.55"
        strokeWidth="1.25"
        strokeLinecap="round"
      />
      <path
        d="M9 12.4l2.1 2.1L15.4 10"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
