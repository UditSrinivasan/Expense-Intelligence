import { NextRequest, NextResponse } from "next/server";
import { authConfigured, createClient } from "../../../lib/supabase/server";

export async function GET(request: NextRequest) {
  if (!authConfigured()) return NextResponse.redirect(new URL("/login?error=configuration", request.url));
  const next = request.nextUrl.searchParams.get("next");
  const destination = next?.startsWith("/") && !next.startsWith("//") ? next : "/onboarding";
  const supabase = await createClient();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${request.nextUrl.origin}/auth/callback?next=${encodeURIComponent(destination)}`, skipBrowserRedirect: true },
  });
  if (error || !data.url) return NextResponse.redirect(new URL("/auth/error", request.url));
  return NextResponse.redirect(data.url);
}
