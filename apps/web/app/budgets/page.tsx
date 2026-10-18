"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Category = { id: string; name: string; parent_id: string | null };
type Contribution = { transaction_id: string; category_id: string | null; description: string; effective_date: string; original_amount: string; original_currency: string; converted_amount: string | null; budget_currency: string; rate: string | null; rate_date: string | null; rate_provider: string | null; excluded_reason: string | null };
type Budget = { id: string; name: string; category_id: string | null; amount: string; currency: string; period_type: "monthly" | "custom"; start_date: string; end_date: string; time_zone: string; warning_percent: string; status: "active" | "archived"; version: number };
type Evaluation = { budget: Budget; spent: string; remaining: string; over_budget: string; utilization_percent: string; warning_state: "ok" | "near_limit" | "over_budget"; complete: boolean; excluded_by_currency: Record<string, string>; conversion_policy: string; previous_period_spent: string; previous_period_difference: string; contributions: Contribution[]; largest_subcategories: { category_id: string; name: string; amount: string }[] };
type Preference = { display_currency: string; time_zone: string };
type Revision = { id: string; version: number; created_at: string; snapshot: { amount: string; currency: string; status: string } };

const apiUrl = "/api/backend";
const headers = { "Content-Type": "application/json" };
const currencies = ["INR", "GBP", "USD", "EUR", "JPY", "KWD"];

function monthBounds(month: string) {
  const [year, number] = month.split("-").map(Number);
  const end = new Date(Date.UTC(year, number, 0));
  return { start: `${month}-01`, end: end.toISOString().slice(0, 10) };
}

export default function BudgetsPage() {
  const [budgets, setBudgets] = useState<Evaluation[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [preference, setPreference] = useState<Preference>({ display_currency: "INR", time_zone: "Asia/Kolkata" });
  const [status, setStatus] = useState("Loading budgets…");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [editing, setEditing] = useState<Budget>();
  const [expanded, setExpanded] = useState<string>();
  const [history, setHistory] = useState<Record<string, Revision[]>>({});
  const [periodType, setPeriodType] = useState<"monthly" | "custom">("monthly");

  async function refresh(showArchived = includeArchived) {
    const response = await fetch(`${apiUrl}/v1/budgets?include_archived=${showArchived}`, { headers });
    if (!response.ok) throw new Error("Budgets could not be loaded.");
    setBudgets(await response.json()); setStatus("Budgets are calculated from approved ledger allocations.");
  }

  useEffect(() => {
    let active = true;
    Promise.all([fetch(`${apiUrl}/v1/budgets`, { headers }), fetch(`${apiUrl}/v1/categories`, { headers }), fetch(`${apiUrl}/v1/preferences`, { headers })]).then(async ([budgetResponse, categoryResponse, preferenceResponse]) => {
      if (!budgetResponse.ok || !categoryResponse.ok || !preferenceResponse.ok) throw new Error("Start the local API to manage budgets.");
      const [nextBudgets, nextCategories, nextPreference] = await Promise.all([budgetResponse.json(), categoryResponse.json(), preferenceResponse.json()]);
      if (active) { setBudgets(nextBudgets); setCategories(nextCategories); setPreference(nextPreference); setStatus("Budgets are calculated from approved ledger allocations."); }
    }).catch((error) => { if (active) setStatus(error.message); });
    return () => { active = false; };
  }, []);

  const categoryNames = useMemo(() => new Map(categories.map((category) => [category.id, category.name])), [categories]);
  const money = (value: string, currency: string) => new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-GB", { style: "currency", currency, maximumFractionDigits: currency === "JPY" ? 0 : currency === "KWD" ? 3 : 2 }).format(Number(value));

  async function saveBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    const period = data.get("period_type") as "monthly" | "custom";
    const bounds = period === "monthly" ? monthBounds(data.get("month")!.toString()) : { start: data.get("start_date")!.toString(), end: data.get("end_date")!.toString() };
    const body = { name: data.get("name"), category_id: data.get("category_id") || null, amount: data.get("amount"), currency: data.get("currency"), period_type: period, start_date: bounds.start, end_date: bounds.end, time_zone: preference.time_zone, warning_percent: data.get("warning_percent") };
    const response = await fetch(editing ? `${apiUrl}/v1/budgets/${editing.id}` : `${apiUrl}/v1/budgets`, { method: editing ? "PUT" : "POST", headers, body: JSON.stringify(editing ? { ...body, expected_version: editing.version } : body) });
    const result = await response.json();
    if (response.ok) { setEditing(undefined); setPeriodType("monthly"); form.reset(); setStatus(editing ? "Budget updated." : "Budget created."); await refresh(); }
    else setStatus(result.detail ?? "Budget could not be saved.");
  }

  async function archiveBudget(budget: Budget) {
    const response = await fetch(`${apiUrl}/v1/budgets/${budget.id}`, { method: "PUT", headers, body: JSON.stringify({ expected_version: budget.version, status: budget.status === "active" ? "archived" : "active" }) });
    if (response.ok) { setStatus(budget.status === "active" ? "Budget archived." : "Budget restored."); await refresh(); }
    else setStatus((await response.json()).detail ?? "Budget status could not be changed.");
  }

  async function removeBudget(budget: Budget) {
    if (!window.confirm(`Delete “${budget.name}”? Its immutable history will be retained for audit.`)) return;
    const response = await fetch(`${apiUrl}/v1/budgets/${budget.id}?expected_version=${budget.version}`, { method: "DELETE", headers });
    if (response.ok) { setStatus("Budget deleted."); await refresh(); }
    else setStatus((await response.json()).detail ?? "Budget could not be deleted.");
  }

  async function showHistory(budget: Budget) {
    const response = await fetch(`${apiUrl}/v1/budgets/${budget.id}/history`, { headers });
    if (response.ok) { const rows = await response.json(); setHistory((current) => ({ ...current, [budget.id]: rows })); setExpanded(budget.id); }
    else setStatus((await response.json()).detail ?? "Budget history could not be loaded.");
  }

  function editBudget(budget: Budget) { setEditing(budget); setPeriodType(budget.period_type); window.scrollTo({ top: 0, behavior: "smooth" }); }
  const editMonth = editing?.start_date.slice(0, 7) ?? "2026-10";

  return <main className="budget-shell" id="main-content">
    <header className="topbar"><Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link><nav className="top-actions"><Link href="/transactions">Transactions</Link><Link href="/assistant">Assistant</Link><div className="environment"><i aria-hidden="true" /> Deterministic budgets</div></nav></header>
    <section className="budget-intro"><div><p className="eyebrow">Allowance planning</p><h1>Budgets grounded in your ledger.</h1><p className="lede">Parent categories include their descendants. Mixed receipts count once. Missing exchange rates remain visible and excluded.</p></div><form key={editing?.id ?? "new"} className="budget-form" onSubmit={saveBudget}>
      <div className="budget-form-heading"><div><p className="eyebrow">{editing ? "Edit budget" : "New budget"}</p><h2>{editing ? editing.name : "Set an allowance"}</h2></div>{editing ? <button className="text-button" type="button" onClick={() => { setEditing(undefined); setPeriodType("monthly"); }}>Cancel</button> : null}</div>
      <label>Name<input name="name" required maxLength={120} autoComplete="off" defaultValue={editing?.name} placeholder="e.g. Monthly transport…" /></label>
      <div className="form-row"><label>Scope<select name="category_id" defaultValue={editing?.category_id ?? ""}><option value="">Overall spending</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.parent_id ? "↳ " : ""}{category.name}</option>)}</select></label><label>Currency<select name="currency" defaultValue={editing?.currency ?? preference.display_currency}>{currencies.map((currency) => <option key={currency}>{currency}</option>)}</select></label></div>
      <div className="form-row"><label>Amount<input name="amount" inputMode="decimal" required defaultValue={editing?.amount} pattern="^\d+(\.\d{1,12})?$" placeholder="0.00…" /></label><label>Warn at %<input name="warning_percent" type="number" min="1" max="100" step="0.01" required defaultValue={editing?.warning_percent ?? "80"} /></label></div>
      <label>Period type<select name="period_type" value={periodType} onChange={(event) => setPeriodType(event.target.value as "monthly" | "custom")}><option value="monthly">Calendar month</option><option value="custom">Custom range</option></select></label>
      {periodType === "monthly" ? <label>Month<input name="month" type="month" required defaultValue={editMonth} /></label> : <div className="form-row"><label>Starts<input name="start_date" type="date" required defaultValue={editing?.start_date} /></label><label>Ends<input name="end_date" type="date" required defaultValue={editing?.end_date} /></label></div>}
      <small>Period boundaries use {preference.time_zone}. Spending uses cached historical daily-reference FX only.</small><button type="submit">{editing ? "Save Budget Changes" : "Create Budget"}</button>
    </form></section>
    <p className="status" role="status" aria-live="polite">{status}</p>
    <section className="budget-ledger"><div className="section-heading"><div><p className="eyebrow">Budget ledger</p><h2>Allowance vs. Spending</h2></div><label className="check"><input type="checkbox" checked={includeArchived} onChange={(event) => { setIncludeArchived(event.target.checked); refresh(event.target.checked).catch((error) => setStatus(error.message)); }} /> Show archived</label></div>
      {budgets.length ? <div className="budget-table">{budgets.map((evaluation) => { const budget = evaluation.budget; const width = Math.min(Number(evaluation.utilization_percent), 100); return <article key={budget.id} className="budget-row">
        <div className="budget-title"><span className={`budget-state ${evaluation.warning_state}`}>{evaluation.warning_state.replaceAll("_", " ")}</span><h3>{budget.name}</h3><p>{budget.category_id ? categoryNames.get(budget.category_id) : "Overall spending"} · {new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(`${budget.start_date}T00:00:00`))}–{new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(`${budget.end_date}T00:00:00`))}</p></div>
        <div className="budget-numbers"><strong>{money(evaluation.spent, budget.currency)} <span>of {money(budget.amount, budget.currency)}</span></strong><small>{evaluation.warning_state === "over_budget" ? `${money(evaluation.over_budget, budget.currency)} over` : `${money(evaluation.remaining, budget.currency)} remaining`}</small></div>
        <div className="progress" aria-label={`${evaluation.utilization_percent}% used`}><i style={{ width: `${width}%` }} /></div>
        <div className="budget-meta"><span>{evaluation.utilization_percent}% used</span><span>{Number(evaluation.previous_period_difference) >= 0 ? "+" : ""}{money(evaluation.previous_period_difference, budget.currency)} vs previous period</span>{!evaluation.complete ? <span className="incomplete">Incomplete · missing FX</span> : null}</div>
        <div className="budget-actions"><button className="secondary" onClick={() => setExpanded(expanded === budget.id ? undefined : budget.id)}>{expanded === budget.id ? "Hide Details" : "View Details"}</button><button className="secondary" onClick={() => showHistory(budget)}>History</button><button className="secondary" onClick={() => editBudget(budget)}>Edit</button><button className="secondary" onClick={() => archiveBudget(budget)}>{budget.status === "active" ? "Archive" : "Restore"}</button><button className="danger" onClick={() => removeBudget(budget)}>Delete</button></div>
        {expanded === budget.id ? <div className="budget-detail"><div><h4>Largest categories</h4>{evaluation.largest_subcategories.length ? <ul>{evaluation.largest_subcategories.map((item) => <li key={item.category_id}><span>{item.name}</span><b>{money(item.amount, budget.currency)}</b></li>)}</ul> : <p>No categorized spending in this period.</p>}{history[budget.id] ? <><h4 className="history-heading">Budget history</h4><ul>{history[budget.id].map((revision) => <li key={revision.id}><span>Version {revision.version}<small>{new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(new Date(revision.created_at))} · {revision.snapshot.status}</small></span><b>{money(revision.snapshot.amount, revision.snapshot.currency)}</b></li>)}</ul></> : null}</div><div><h4>Contributing transactions</h4>{evaluation.contributions.length ? <ul>{evaluation.contributions.map((item) => <li key={`${item.transaction_id}-${item.category_id}`}><span>{item.description}<small>{item.original_currency === budget.currency ? "Original currency" : item.excluded_reason ?? `${item.rate_provider} · ${item.rate_date}`}</small></span><b>{item.converted_amount === null ? "Excluded" : money(item.converted_amount, budget.currency)}</b></li>)}</ul> : <p>No contributing transactions.</p>}</div><p className="fx-policy">{evaluation.conversion_policy}</p></div> : null}
      </article>; })}</div> : <div className="empty"><span>00</span><h3>No budgets yet</h3><p>Create an overall or category budget. Spending remains available without AI.</p></div>}
    </section>
  </main>;
}
