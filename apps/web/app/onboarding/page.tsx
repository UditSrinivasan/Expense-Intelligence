import { ProfileForm } from "../profile-form";

export default function OnboardingPage() {
  return <main id="main-content" className="auth-shell"><section className="auth-card wide">
    <p className="eyebrow">First-time setup</p><h1>Make the ledger yours.</h1>
    <p className="lede">Choose these explicitly—we never infer your country or currency from your IP address.</p>
    <ProfileForm onboarding />
  </section></main>;
}
