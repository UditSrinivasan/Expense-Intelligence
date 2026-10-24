import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { isInvited } from "./invites";

const publicPaths = ["/login", "/auth/login", "/auth/callback", "/auth/error"];

export async function updateSession(request: NextRequest) {
  const configured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  const localDevelopment = process.env.NODE_ENV === "development" && Boolean(process.env.NEXT_PUBLIC_DEV_USER_ID);
  if (!configured) {
    if (localDevelopment || publicPaths.some((path) => request.nextUrl.pathname.startsWith(path))) return NextResponse.next();
    return NextResponse.redirect(new URL("/login?error=configuration", request.url));
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(values, headers) {
        values.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        values.forEach(({ name, value, options }) => response.cookies.set(name, value, { ...options, httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production" }));
        for (const [name, value] of Object.entries(headers ?? {})) response.headers.set(name, value);
      },
    },
  });
  const { data, error } = await supabase.auth.getClaims();
  const claims = data?.claims;
  const signedIn = !error && Boolean(claims?.sub);
  if (claims?.sub && !error && !isInvited(claims)) {
    await supabase.auth.signOut({ scope: "local" });
    const denied = NextResponse.redirect(new URL("/auth/error?reason=not_invited", request.url));
    response.cookies.getAll().forEach(cookie => denied.cookies.set(cookie));
    denied.headers.set("Cache-Control", "private, no-store");
    return denied;
  }
  const isPublic = publicPaths.some((path) => request.nextUrl.pathname.startsWith(path));
  if (!signedIn && !isPublic) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    const redirect = NextResponse.redirect(login);
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
    redirect.headers.set("Cache-Control", "private, no-store");
    return redirect;
  }
  if (signedIn && request.nextUrl.pathname === "/login") return NextResponse.redirect(new URL("/", request.url));
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
