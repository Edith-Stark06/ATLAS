import { NextResponse } from "next/server";

import { PROFILE_COOKIE, SESSION_COOKIE } from "@/lib/session-cookies";

export async function POST(request: Request) {
  const response = NextResponse.redirect(new URL("/login", request.url), { status: 303 });
  // Clearing both: leaving the profile cookie behind would show a signed-in
  // name in the header for a session that no longer exists.
  response.cookies.delete(SESSION_COOKIE);
  response.cookies.delete(PROFILE_COOKIE);
  return response;
}
