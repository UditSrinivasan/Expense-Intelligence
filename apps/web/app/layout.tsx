import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppShell } from "./app-shell";

export const metadata: Metadata = {
  title: "Expense Intelligence",
  description: "Private, currency-aware spending clarity for India and the UK.",
};
export const viewport: Viewport = { themeColor: "#f5f3ee" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body><a className="skip-link" href="#main-content">Skip to main content</a><AppShell>{children}</AppShell></body>
    </html>
  );
}
