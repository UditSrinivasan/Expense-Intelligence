import { type NextRequest, NextResponse } from "next/server";
import { hostedConfigurationError } from "../../../../lib/deployment-env";
import { authConfigured, createClient } from "../../../../lib/supabase/server";

const allowedMethods = ["GET", "POST", "PUT", "DELETE"];

async function forward(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (hostedConfigurationError()) return NextResponse.json({ detail: "Hosted configuration is incomplete" }, { status: 503 });
  if (!allowedMethods.includes(request.method)) return NextResponse.json({ detail: "Method not allowed" }, { status: 405 });
  if (request.method !== "GET" && request.headers.get("origin") !== request.nextUrl.origin) {
    return NextResponse.json({ detail: "Invalid request origin" }, { status: 403 });
  }

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  if (authConfigured()) {
    const supabase = await createClient();
    const { data: claims, error } = await supabase.auth.getClaims();
    if (error || !claims?.claims?.sub) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
    const { data } = await supabase.auth.getSession();
    if (!data.session?.access_token) return NextResponse.json({ detail: "Session expired" }, { status: 401 });
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  } else if (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_DEV_USER_ID) {
    headers.set("X-Dev-User-Id", process.env.NEXT_PUBLIC_DEV_USER_ID);
  } else {
    return NextResponse.json({ detail: "Hosted authentication is not configured" }, { status: 503 });
  }

  const { path } = await params;
  const apiUrl = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const upstream = await fetch(`${apiUrl}/${path.join("/")}${request.nextUrl.search}`, {
    method: request.method,
    headers,
    body: request.method === "GET" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    signal: AbortSignal.timeout(30_000),
  });
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store" },
  });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const DELETE = forward;
