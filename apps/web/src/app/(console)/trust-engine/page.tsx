import { ShieldCheck } from "lucide-react";

import { ComingSoon } from "@/components/ui/coming-soon";

export const metadata = { title: "Trust Engine — ATLAS" };

export default function Page() {
  return (
    <ComingSoon
      title="Trust"
      highlight="Engine"
      description="Continuous computation of every agent’s trust score from behavioural, contextual, policy and risk signals."
      icon={ShieldCheck}
      phase="Phase 3"
      capabilities={[
        "Live trust score computation and factor weighting",
        "Behavioural drift and anomaly detection",
        "Trust history timelines per agent",
        "Threshold configuration per action class",
      ]}
    />
  );
}
