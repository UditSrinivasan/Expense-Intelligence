"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";
type Accent = "ocean" | "emerald" | "violet" | "amber" | "coral" | "slate";
type Profile = { display_name:string; country_code:string; locale:string; home_currency:string; display_currency:string; time_zone:string; theme:Theme; accent:Accent };
const accents: { value: Accent; label: string }[] = [{value:"ocean",label:"Ocean Blue"},{value:"emerald",label:"Emerald"},{value:"violet",label:"Violet"},{value:"amber",label:"Amber"},{value:"coral",label:"Coral"},{value:"slate",label:"Slate"}];

function apply(theme: Theme, accent: Accent) {
  const resolved = theme === "system" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : theme;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = theme;
  document.documentElement.dataset.accent = accent;
  document.documentElement.style.colorScheme = resolved;
  localStorage.setItem("ei-appearance-v1", JSON.stringify({ theme, accent }));
}

export function ThemeControls() {
  const [profile, setProfile] = useState<Profile>();
  const [status, setStatus] = useState("Loading appearance…");
  useEffect(() => {
    fetch("/api/backend/v1/profile").then(async response => {
      if (!response.ok) throw new Error("Appearance could not be loaded.");
      return response.json() as Promise<Profile>;
    }).then(value => { setProfile(value); apply(value.theme, value.accent); setStatus(""); }).catch(error => setStatus(error.message));
  }, []);
  useEffect(() => {
    if (!profile || profile.theme !== "system") return;
    const media = matchMedia("(prefers-color-scheme: dark)"), update = () => apply("system", profile.accent);
    media.addEventListener("change", update); return () => media.removeEventListener("change", update);
  }, [profile]);
  async function save(theme: Theme, accent: Accent) {
    if (!profile) return;
    const next = { ...profile, theme, accent }; setProfile(next); apply(theme, accent); setStatus("Saving…");
    const response = await fetch("/api/backend/v1/profile", { method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify(next) });
    setStatus(response.ok ? "Appearance saved." : "Appearance could not be saved. Try again.");
  }
  return <section className="appearance-settings" aria-labelledby="appearance-title">
    <div><p className="eyebrow">Personalize</p><h2 id="appearance-title">Appearance</h2><p>Choose a theme and accent. Financial status colors keep their meaning.</p></div>
    <fieldset><legend>Theme</legend><div className="segmented-control">{(["light","dark","system"] as Theme[]).map(theme => <button disabled={!profile} type="button" aria-pressed={profile?.theme === theme} key={theme} onClick={() => profile && void save(theme, profile.accent)}>{theme[0].toUpperCase()+theme.slice(1)}</button>)}</div></fieldset>
    <fieldset><legend>Accent color</legend><div className="accent-grid">{accents.map(accent => <button disabled={!profile} type="button" aria-pressed={profile?.accent === accent.value} key={accent.value} onClick={() => profile && void save(profile.theme, accent.value)}><span data-accent-swatch={accent.value} aria-hidden="true"/>{accent.label}</button>)}</div></fieldset>
    <p className="status" role="status" aria-live="polite">{status}</p>
  </section>;
}
