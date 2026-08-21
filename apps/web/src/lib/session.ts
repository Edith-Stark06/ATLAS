import "server-only";

import { cookies } from "next/headers";

import { PROFILE_COOKIE, SESSION_COOKIE } from "@/lib/session-cookies";

/**
 * The access token lives in an httpOnly cookie, so browser JavaScript can
 * never read it — an XSS bug then cannot exfiltrate a working credential.
 *
 * The cost is that client components cannot call the API directly with it,
 * which is why browser-side requests go through the proxy route handler in
 * `app/api/atlas/[...path]`. That is the trade being made deliberately:
 * one extra hop in exchange for a token that script cannot touch.
 */
export interface Session {
  token: string;
  role: string;
  name: string;
  email: string;
}

export async function getToken(): Promise<string | null> {
  return (await cookies()).get(SESSION_COOKIE)?.value ?? null;
}

/**
 * Display-only identity, in a readable cookie.
 *
 * Deliberately separate from the token and never trusted for authorisation:
 * it decides whether to render an "Admin" chip, nothing more. Every actual
 * permission check happens in the API against the token.
 */
export async function getSession(): Promise<Session | null> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  if (!token) return null;

  const raw = store.get(PROFILE_COOKIE)?.value;
  if (!raw) return { token, role: "viewer", name: "Signed in", email: "" };

  try {
    const profile = JSON.parse(decodeURIComponent(raw)) as Omit<Session, "token">;
    return { token, ...profile };
  } catch {
    // A malformed profile cookie is cosmetic — do not fail the request over it.
    return { token, role: "viewer", name: "Signed in", email: "" };
  }
}

