import Link from "next/link";

type Props = { searchParams: Promise<{ reason?: string }> };

export default async function AuthErrorPage({ searchParams }: Props) {
  const denied = (await searchParams).reason === "not_invited";
  return <main id="main-content" className="auth-shell"><section className="auth-card">
    <p className="eyebrow">{denied ? "Invitation required" : "Authentication error"}</p><h1>{denied ? "This demo is invite-only." : "We couldn’t sign you in."}</h1>
    <p className="lede">{denied ? "This Google account is not on the approved tester list. Ask the demo owner to invite the exact email address you used." : "The authorization code may have expired or already been used. Start a fresh sign-in attempt."}</p>
    <Link className="primary-button" href="/login">Return to sign in</Link>
  </section></main>;
}
