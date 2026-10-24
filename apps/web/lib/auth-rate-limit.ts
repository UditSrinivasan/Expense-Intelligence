import { NextRequest, NextResponse } from "next/server";

const attempts = new Map<string, { count: number; reset: number }>();

export function limitAuthRequest(request: NextRequest, maximum = 10) {
  const now = Date.now(), windowMs = 10 * 60 * 1000;
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const key = forwarded || request.headers.get("x-real-ip") || "unknown";
  const current = attempts.get(key);
  const entry = !current || current.reset <= now ? { count: 1, reset: now + windowMs } : { ...current, count: current.count + 1 };
  attempts.set(key, entry);
  if (attempts.size > 10_000) for (const [item, value] of attempts) if (value.reset <= now) attempts.delete(item);
  if (entry.count <= maximum) return null;
  const retry = Math.max(1, Math.ceil((entry.reset - now) / 1000));
  return NextResponse.json({ detail: "Too many authentication attempts; retry later" }, { status: 429, headers: { "Retry-After": String(retry) } });
}
