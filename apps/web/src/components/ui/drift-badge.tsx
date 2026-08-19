import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import { StatusChip } from "@/components/ui/status-chip";
import type { Drift } from "@/lib/types";

/** Shows movement against the agent's own baseline, not an absolute score. */
export function DriftBadge({ drift }: { drift: Drift }) {
  if (drift.baseline === null) {
    return <StatusChip tone="neutral">No history</StatusChip>;
  }

  if (drift.detected) {
    return (
      <StatusChip tone="danger">
        <TrendingDown className="size-3" />
        Drift {drift.delta.toFixed(1)}
      </StatusChip>
    );
  }

  if (drift.delta > 0.5) {
    return (
      <StatusChip tone="success">
        <TrendingUp className="size-3" />+{drift.delta.toFixed(1)}
      </StatusChip>
    );
  }

  return (
    <StatusChip tone="neutral">
      <Minus className="size-3" />
      Stable
    </StatusChip>
  );
}
