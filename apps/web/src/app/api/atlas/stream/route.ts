import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { getToken } from "@/lib/session";

/**
 * Proxies the live activity feed (GET /api/v1/activity/stream, Server-Sent
 * Events) to the browser — a dedicated route rather than a branch inside
 * ../[...path]/route.ts, which is deliberately kept a fully-buffering
 * passthrough (`await request.text()` in, `await upstream.text()` out) for
 * the ordinary request/response case it handles correctly today; adding a
 * streaming branch there would complicate a file that works.
 *
 * Same reason this exists at all as the other proxy: a browser-native
 * EventSource cannot set an Authorization header, so it cannot call the
 * ATLAS API directly. It doesn't need to — same-origin means the browser
 * sends the session cookie automatically, and the token is attached here,
 * server-side, exactly like every other browser->API call in this app.
 */
export async function GET() {
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/v1/activity/stream`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Cannot reach ATLAS API at ${API_BASE_URL} — ${message}` },
      { status: 502 },
    );
  }

  // Piped straight through as a ReadableStream, not buffered — the whole
  // point of this route. An open SSE connection never ends on its own, so
  // buffering it (as ../[...path]/route.ts does) would hang forever
  // waiting for a response body that's never going to finish.
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
