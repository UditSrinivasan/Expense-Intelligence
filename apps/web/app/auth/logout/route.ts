import { NextRequest, NextResponse } from "next/server";
import { createClient } from "../../../lib/supabase/server";
import { limitAuthRequest } from "../../../lib/auth-rate-limit";

export async function POST(request: NextRequest) {
  const limited = limitAuthRequest(request, 20);
  if (limited) return limited;
  if (request.headers.get("origin") !== request.nextUrl.origin) return NextResponse.json({ detail: "Invalid request origin" }, { status: 403 });
  const supabase = await createClient();
  await supabase.auth.signOut({ scope: "local" });
  return NextResponse.redirect(new URL("/login", request.url), 303);
}
