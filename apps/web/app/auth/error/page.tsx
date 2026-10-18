import Link from "next/link";

export default function AuthErrorPage() {
  return <main id="main-content" className="auth-shell"><section className="auth-card">
    <p className="eyebrow">Authentication error</p><h1>We couldn’t sign you in.</h1>
    <p className="lede">The authorization code may have expired or already been used. Start a fresh sign-in attempt.</p>
    <Link className="primary-button" href="/login">Return to sign in</Link>
  </section></main>;
}
