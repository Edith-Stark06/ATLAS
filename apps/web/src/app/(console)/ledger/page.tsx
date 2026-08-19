import { ScrollText } from "lucide-react";

import { ComingSoon } from "@/components/ui/coming-soon";

export const metadata = { title: "Governance Ledger — ATLAS" };

export default function Page() {
  return (
    <ComingSoon
      title="Governance"
      highlight="Ledger"
      description="An immutable, auditable record of every decision, policy version, and trust state at time of execution."
      icon={ScrollText}
      phase="Phase 6"
      capabilities={[
        "Append-only decision records",
        "Policy version pinning per decision",
        "Cryptographic integrity verification",
        "Regulator-ready audit exports",
      ]}
    />
  );
}
