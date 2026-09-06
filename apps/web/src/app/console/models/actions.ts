"use server";

import { revalidatePath } from "next/cache";

import { reloadModels } from "@/lib/api";

/**
 * Swaps the running process onto whatever artifacts are currently on disk.
 *
 * The API enforces the admin requirement; this is only the form target. A
 * promotion done on the box does nothing to a live server until this runs,
 * because every model loader is cached for the process's whole life.
 */
export async function runReloadModels() {
  await reloadModels();
  revalidatePath("/console/models");
  revalidatePath("/console/trust-engine");
}
