import { Lightbulb } from "lucide-react";

import { ComingSoon } from "@/components/ui/coming-soon";

export const metadata = { title: "Explain AI — ATLAS" };

export default function Page() {
  return (
    <ComingSoon
      title="Explain"
      highlight="AI"
      description="Human-readable explanations for every governance decision, grounded in the evidence that produced it."
      icon={Lightbulb}
      phase="Phase 6"
      capabilities={[
        "Natural-language rationale for each verdict",
        "Contributing trust factors and their weights",
        "Counterfactuals — what would have changed the outcome",
        "Exportable explanations for auditors",
      ]}
    />
  );
}
