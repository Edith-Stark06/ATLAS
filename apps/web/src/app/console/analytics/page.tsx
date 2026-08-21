import { BarChart3 } from "lucide-react";

import { ComingSoon } from "@/components/ui/coming-soon";

export const metadata = { title: "Governance Analytics — ATLAS" };

export default function Page() {
  return (
    <ComingSoon
      title="Governance"
      highlight="Analytics"
      description="Aggregate trends across agents, policies, and decisions over time."
      icon={BarChart3}
      phase="Phase 7"
      capabilities={[
        "Trust score distribution across the agent estate",
        "Policy violation trends and hot spots",
        "Human review load and turnaround",
        "Cost and latency of governance overhead",
      ]}
    />
  );
}
