import { Bell } from "lucide-react";

import { ComingSoon } from "@/components/ui/coming-soon";

export const metadata = { title: "Alerts & Escalations — ATLAS" };

export default function Page() {
  return (
    <ComingSoon
      title="Alerts"
      highlight="& Escalations"
      description="Real-time notification when an agent degrades, a policy trips, or a decision needs a human."
      icon={Bell}
      phase="Phase 6"
      capabilities={[
        "Trust degradation and drift alerts",
        "Escalation queue with clearance routing",
        "Policy breach notifications",
        "On-call integration and acknowledgement",
      ]}
    />
  );
}
