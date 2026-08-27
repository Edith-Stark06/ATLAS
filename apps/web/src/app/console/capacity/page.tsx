import { CapacityPlanner } from "@/components/capacity/capacity-planner";
import { ApiError } from "@/components/ui/api-error";
import { PageHeader } from "@/components/ui/page-header";
import { fetchCohorts, tryFetch } from "@/lib/api";

export const metadata = { title: "Capacity Planning — ATLAS" };
export const dynamic = "force-dynamic";

export default async function CapacityPage() {
  const cohorts = await tryFetch(fetchCohorts);

  const header = (
    <PageHeader
      title="Capacity"
      highlight="Planning"
      description="What growing a job would demand of governance — how much human review it needs, which agents can safely take the extra work, and which constraint runs out first."
    />
  );

  if (!cohorts.ok) {
    return (
      <>
        {header}
        <ApiError error={cohorts.error} />
      </>
    );
  }

  if (cohorts.data.length === 0) {
    return (
      <>
        {header}
        <ApiError error="No agents registered — nothing to plan capacity for." />
      </>
    );
  }

  return (
    <>
      {header}
      <CapacityPlanner cohorts={cohorts.data} />
    </>
  );
}
