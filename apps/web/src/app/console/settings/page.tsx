import { Settings } from "lucide-react";

import { ComingSoon } from "@/components/ui/coming-soon";

export const metadata = { title: "Platform Settings — ATLAS" };

export default function Page() {
  return (
    <ComingSoon
      title="Platform"
      highlight="Settings"
      description="Tenant configuration, access control, and integration management."
      icon={Settings}
      phase="Phase 7"
      capabilities={[
        "Role-based access control",
        "Environment and tenant configuration",
        "API keys and service integrations",
        "Retention and data residency policy",
      ]}
    />
  );
}
