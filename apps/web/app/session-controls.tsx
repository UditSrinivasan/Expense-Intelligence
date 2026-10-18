"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function SessionControls() {
  const pathname = usePathname();
  const configured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  if (pathname === "/login" || pathname.startsWith("/auth/")) return null;
  return <div className="session-controls" aria-label="Account controls">
    <Link href="/settings">Account</Link>
    {configured ? <form action="/auth/logout" method="post"><button type="submit">Sign out</button></form> : null}
  </div>;
}
