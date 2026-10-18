import Link from "next/link";
import { ProfileForm } from "../profile-form";

export default function SettingsPage() {
  return <main id="main-content"><header className="topbar"><Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link></header>
    <section className="settings-header"><p className="eyebrow">Account</p><h1>Your preferences</h1><p className="lede">These settings affect formatting and defaults, never authorization.</p></section>
    <section className="panel settings-panel"><ProfileForm /></section>
  </main>;
}
