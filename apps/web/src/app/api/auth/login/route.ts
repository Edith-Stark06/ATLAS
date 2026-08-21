import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { PROFILE_COOKIE, SESSION_COOKIE } from "@/lib/session-cookies";

/**
 * Exchanges credentials for a session cookie.
 *
 * The password reaches the ATLAS API from *this* server, never from the
 * browser to the API directly, and the token comes back into an httpOnly
 * cookie that page scripts cannot read.
 */
export async function POST(request: Request) {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Malformed request" }, { status: 400 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({ email: body.email, password: body.password }),
    });
  } catch {
    return NextResponse.json(
      { error: `Cannot reach the ATLAS API at ${API_BASE_URL}` },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    // Pass the API's own wording through — it is deliberately generic, so it
    // cannot be used to work out whether an account exists.
    const detail = await upstream
      .json()
      .then((b) => (typeof b?.detail === "string" ? b.detail : "Invalid email or password"))
      .catch(() => "Invalid email or password");
    return NextResponse.json({ error: detail }, { status: upstream.status });
  }

  const session = await upstream.json();
  const response = NextResponse.json({ ok: true, role: session.role });
  const secure = process.env.NODE_ENV === "production";

  response.cookies.set(SESSION_COOKIE, session.accessToken, {
    httpOnly: true,
    sameSite: "lax",
    // Only over HTTPS in production; local development is plain HTTP, where
    // this flag would stop the cookie being set at all.
    secure,
    path: "/",
    maxAge: session.expiresInSeconds,
  });

  // Readable, and used only for display. Never for an access decision.
  response.cookies.set(
    PROFILE_COOKIE,
    encodeURIComponent(
      JSON.stringify({ role: session.role, name: session.name, email: session.email }),
    ),
    { httpOnly: false, sameSite: "lax", secure, path: "/", maxAge: session.expiresInSeconds },
  );

  return response;
}
