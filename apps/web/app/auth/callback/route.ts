import { NextRequest, NextResponse } from "next/server";
import { createClient } from "../../../lib/supabase/server";
import { limitAuthRequest } from "../../../lib/auth-rate-limit";
import { isInvited } from "../../../lib/supabase/invites";

export async function GET(request: NextRequest) {
  const limited = limitAuthRequest(request, 20);
  if (limited) return limited;
  const code = request.nextUrl.searchParams.get("code");
  const requested = request.nextUrl.searchParams.get("next");
  const next = requested?.startsWith("/") && !requested.startsWith("//") ? requested : "/onboarding";
  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      const { data } = await supabase.auth.getClaims();
      if (data?.claims && isInvited(data.claims)) return NextResponse.redirect(new URL(next, request.url));
      await supabase.auth.signOut({ scope: "local" });
      return NextResponse.redirect(new URL("/auth/error?reason=not_invited", request.url));
    }
  }
  return NextResponse.redirect(new URL("/auth/error", request.url));
}
