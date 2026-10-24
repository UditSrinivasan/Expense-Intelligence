import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppShell } from "./app-shell";
import Script from "next/script";

export const metadata: Metadata = {
  title: "Expense Intelligence",
  description: "Private, currency-aware spending clarity for India and the UK.",
};
export const viewport: Viewport = { themeColor: "#f5f3ee" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth" suppressHydrationWarning>
      <body><Script id="appearance" strategy="beforeInteractive">{`try{const p=JSON.parse(localStorage.getItem('ei-appearance-v1')||'{}');const t=p.theme==='system'||!p.theme?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):p.theme;document.documentElement.dataset.theme=t;document.documentElement.dataset.themePreference=p.theme||'system';document.documentElement.dataset.accent=p.accent||'ocean';document.documentElement.style.colorScheme=t}catch{}`}</Script><a className="skip-link" href="#main-content">Skip to main content</a><AppShell>{children}</AppShell></body>
    </html>
  );
}
