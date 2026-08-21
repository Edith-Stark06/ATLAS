"use server";

import { revalidatePath } from "next/cache";

import { recomputeTrust } from "@/lib/api";

/**
 * Runs a fresh evaluation across the estate. Every agent gets a new snapshot,
 * which is also what feeds drift detection and forecasting on the next read.
 */
export async function runRecompute() {
  await recomputeTrust();
  revalidatePath("/console/trust-engine");
  revalidatePath("/console/agents");
  revalidatePath("/console");
}
