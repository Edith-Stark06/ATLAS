import { NextResponse } from "next/server";

import { API_BASE_URL } from "@/lib/api";
import { getToken } from "@/lib/session";

/**
 * Attaches the session token to browser-originated API calls.
 *
 * Client components cannot read the httpOnly session cookie — that is the
 * point of it — so they call this route instead and the token is added here,
 * server-side. Without this, the only way for interactive components to
 * authenticate would be a token readable by page scripts, and any XSS bug
 * would hand an attacker a working credential.
 *
 * This is a credential-attaching proxy, not an open one: the upstream host is
 * fixed to API_BASE_URL and only the path is taken from the request, so it
 * cannot be pointed at an arbitrary target.
 */
async function proxy(request: Request, path: string[]): Promise<Response> {
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const search = new URL(request.url).search;
  const target = `${API_BASE_URL}/api/v1/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      cache: "no-store",
      body: hasBody ? await request.text() : undefined,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: `Cannot reach ATLAS API at ${API_BASE_URL} — ${message}` },
      { status: 502 },
    );
  }

  const body = await upstream.text();
  return new NextResponse(body, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
    },
  });
}

type Context = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, { params }: Context) {
  return proxy(request, (await params).path);
}

export async function POST(request: Request, { params }: Context) {
  return proxy(request, (await params).path);
}

export async function DELETE(request: Request, { params }: Context) {
  return proxy(request, (await params).path);
}
