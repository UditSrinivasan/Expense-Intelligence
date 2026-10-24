import Link from "next/link";
import { ProfileForm } from "../profile-form";
import { ThemeControls } from "../theme-controls";

export default function SettingsPage() {
  return <main id="main-content"><header className="topbar"><Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link></header>
    <section className="settings-header"><p className="eyebrow">Account</p><h1>Your preferences</h1><p className="lede">These settings affect formatting and defaults, never authorization.</p></section>
    <section className="panel settings-panel"><ProfileForm /><ThemeControls/><div className="context-help"><h2>Privacy by default</h2><p>Your profile controls formatting, not authorization. Financial endpoints use your verified server-side identity. The assistant lab remains synthetic and disconnected from private records while agent mode is disabled.</p><Link href="/assistant">Review assistant memory status</Link></div></section>
  </main>;
}
