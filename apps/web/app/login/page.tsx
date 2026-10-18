import Link from "next/link";

type Props = { searchParams: Promise<{ error?: string; next?: string }> };

export default async function LoginPage({ searchParams }: Props) {
  const query = await searchParams;
  const next = query.next?.startsWith("/") && !query.next.startsWith("//") ? query.next : "/onboarding";
  const configured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  const message = !configured || query.error === "configuration"
    ? "Supabase authentication is not configured for this environment."
    : query.error ? "Sign-in could not be completed. Please try again." : "";
  return <main id="main-content" className="auth-shell">
    <section className="auth-card" aria-labelledby="login-title">
      <Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link>
      <p className="eyebrow">Private by design</p>
      <h1 id="login-title">Your finances,<br />for your eyes only.</h1>
      <p className="lede">Sign in securely through Google. Expense Intelligence never receives your Google password.</p>
      {message ? <p className="status error" role="alert">{message}</p> : null}
      {configured ? <a className="google-button" href={`/auth/login?next=${encodeURIComponent(next)}`}><span aria-hidden="true">G</span> Continue with Google</a>
        : <button className="google-button disabled" type="button" disabled><span aria-hidden="true">G</span> Continue with Google</button>}
      <p className="auth-note">Sessions use Supabase Auth with authorization code and PKCE. No financial records are sent to Google.</p>
    </section>
  </main>;
}
