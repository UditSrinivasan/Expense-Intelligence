"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ProductGuide } from "./product-guide";

const destinations = [
  { href: "/", label: "Overview", mark: "OV" },
  { href: "/transactions", label: "Transactions", mark: "TR" },
  { href: "/budgets", label: "Budgets", mark: "BU" },
  { href: "/groups", label: "Groups", mark: "GR" },
  { href: "/#insights", label: "Insights", mark: "IN" },
  { href: "/imports", label: "Imports & Documents", mark: "IM" },
  { href: "/assistant", label: "Assistant", mark: "AI" },
  { href: "/settings", label: "Settings", mark: "SE" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/#insights") return false;
  if (href === "/imports") return pathname.startsWith("/imports") || pathname.startsWith("/documents");
  return pathname === href || pathname.startsWith(`${href}/`);
}

function Navigation({ pathname }: { pathname: string }) {
  return <nav className="app-nav" aria-label="Primary navigation">
    {destinations.map((item) => <Link href={item.href} key={item.label} data-tour={`nav-${item.mark.toLowerCase()}`} aria-current={isActive(pathname, item.href) ? "page" : undefined}>
      <span aria-hidden="true">{item.mark}</span>{item.label}
    </Link>)}
  </nav>;
}

function Breadcrumbs({ pathname }: { pathname: string }) {
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length) return null;
  const labels: Record<string, string> = { transactions: "Transactions", budgets: "Budgets", groups: "Groups", imports: "Imports", documents: "Documents", assistant: "Assistant", settings: "Settings", expenses: "Expenses", "new-expense": "New Expense" };
  const crumbs = parts.map((part, index) => {
    const groupId = parts[0] === "groups" && index === 1;
    const expenseId = parts[index - 1] === "expenses";
    return { href: `/${parts.slice(0, index + 1).join("/")}`, label: labels[part] ?? (groupId ? "Workspace" : expenseId ? "Expense Details" : part) };
  });
  return <nav className="breadcrumbs" aria-label="Breadcrumb"><ol><li><Link href="/">Overview</Link></li>{crumbs.map((crumb, index) => <li key={crumb.href}>{index === crumbs.length - 1 ? <span aria-current="page">{crumb.label}</span> : <Link href={crumb.href}>{crumb.label}</Link>}</li>)}</ol></nav>;
}

function AccountActions() {
  const configured = Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
  return <div className="account-actions"><Link href="/settings"><span className="account-avatar" aria-hidden="true">EI</span><span><strong>Account</strong><small>Preferences & privacy</small></span></Link>{configured ? <form action="/auth/logout" method="post"><button type="submit">Sign Out</button></form> : null}</div>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  if (pathname === "/login" || pathname.startsWith("/auth/") || pathname === "/onboarding") return children;
  return <div className="app-shell">
    <aside className="app-sidebar">
      <Link className="app-brand" href="/"><span>EI</span><strong>Expense<br/>Intelligence</strong></Link>
      <Navigation pathname={pathname}/>
      <AccountActions/>
    </aside>
    <header className="mobile-app-header">
      <Link className="app-brand" href="/"><span>EI</span><strong>Expense Intelligence</strong></Link>
      <details className="mobile-menu"><summary aria-label="Open navigation">Open navigation</summary><Navigation pathname={pathname}/><AccountActions/></details>
    </header>
    <div className="app-content"><Breadcrumbs pathname={pathname}/>{children}</div>
    <ProductGuide pathname={pathname}/>
  </div>;
}
