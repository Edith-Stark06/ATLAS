import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/session-cookies";

/**
 * Gates the console behind a session.
 *
 * This is a redirect for unauthenticated *navigation*, not an authorisation
 * check — the presence of a cookie proves nothing. Every request still carries
 * the token to the ATLAS API, which validates it and enforces the caller's
 * role. Treating this file as the security boundary would mean anyone who can
 * set a cookie named `atlas_session` gets in.
 *
 * Next.js 16 renamed the `middleware` convention to `proxy`; the behaviour is
 * unchanged.
 */
export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const signedIn = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (!signedIn) {
    const login = new URL("/login", request.url);
    // Preserve where they were heading so sign-in lands them there.
    login.searchParams.set("next", pathname + search);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  // Only the console. The landing page is public, and /login must stay
  // reachable or an expired session would be an infinite redirect.
  matcher: ["/console/:path*"],
};
