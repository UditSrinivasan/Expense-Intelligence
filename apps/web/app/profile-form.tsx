"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Profile = { display_name:string; country_code:"IN"|"GB"; locale:"en-IN"|"en-GB"; home_currency:string; display_currency:string; time_zone:string; onboarding_completed:boolean };
const defaults: Profile = { display_name:"", country_code:"IN", locale:"en-IN", home_currency:"INR", display_currency:"INR", time_zone:"Asia/Kolkata", onboarding_completed:false };

export function ProfileForm({ onboarding = false }: { onboarding?: boolean }) {
  const router = useRouter();
  const [profile, setProfile] = useState(defaults);
  const [status, setStatus] = useState("Loading profile…");
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/backend/v1/profile", { signal: controller.signal }).then(async response => {
      if (response.status === 401) { router.replace("/login?error=expired"); return null; }
      if (!response.ok) throw new Error("Profile could not be loaded.");
      return response.json() as Promise<Profile>;
    }).then(data => { if (data) { setProfile(data); setStatus(""); setLoaded(true); if (onboarding && data.onboarding_completed) router.replace("/"); } }).catch(error => { if (error.name !== "AbortError") setStatus(error.message); });
    return () => controller.abort();
  }, [onboarding, router]);

  function selectCountry(country: "IN"|"GB") {
    setProfile(current => ({ ...current, country_code:country, locale:country === "IN" ? "en-IN" : "en-GB", home_currency:country === "IN" ? "INR" : "GBP", display_currency:country === "IN" ? "INR" : "GBP", time_zone:country === "IN" ? "Asia/Kolkata" : "Europe/London" }));
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setStatus("Saving…");
    const response = await fetch("/api/backend/v1/profile", { method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(profile) });
    setSaving(false);
    if (!response.ok) { setStatus(response.status === 401 ? "Your session expired. Sign in again." : "Profile could not be saved. Check the fields and try again."); return; }
    setStatus("Profile saved.");
    if (onboarding) router.replace("/");
  }
  return <form className="profile-form" onSubmit={submit}>
    <label>Display name<input name="display_name" required maxLength={120} autoComplete="name" value={profile.display_name} onChange={event=>setProfile({...profile,display_name:event.target.value})}/></label>
    <label>Country<select name="country_code" autoComplete="country" value={profile.country_code} onChange={event=>selectCountry(event.target.value as "IN"|"GB")}><option value="IN">India</option><option value="GB">United Kingdom</option></select></label>
    <label>Home currency<select name="home_currency" autoComplete="off" value={profile.home_currency} onChange={event=>setProfile({...profile,home_currency:event.target.value,display_currency:event.target.value})}><option>INR</option><option>GBP</option><option>USD</option><option>EUR</option></select></label>
    <label>Time zone<select name="time_zone" autoComplete="off" value={profile.time_zone} onChange={event=>setProfile({...profile,time_zone:event.target.value})}><option value="Asia/Kolkata">India — Asia/Kolkata</option><option value="Europe/London">UK — Europe/London</option></select></label>
    <button className="primary-button" type="submit" disabled={saving || !loaded}>{saving ? "Saving…" : onboarding ? "Finish setup" : "Save changes"}</button>
    <p className="status" role="status" aria-live="polite">{status}</p>
  </form>;
}
