"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Category = { id: string; name: string; parent_id: string | null; owner_user_id: string | null };
type Transaction = { id: string; description: string; category: string; classification_source: string; original_amount: string; original_currency: string; effective_date: string; needs_review: boolean };
type Rule = { id: string; match_value: string; merchant_name: string | null; category_id: string; active: boolean; evidence_count: number };
type BulkPreview = { eligible_transaction_ids: string[]; rejected: Record<string, string>; totals_by_currency: Record<string, string>; category: Category };

const apiUrl = "/api/backend";
const headers = { "Content-Type": "application/json" };

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [rules, setRules] = useState<Rule[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("Loading finance records…");
  const [saving, setSaving] = useState<string>();
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkCategory, setBulkCategory] = useState("");
  const [bulkPreview, setBulkPreview] = useState<BulkPreview>();

  async function refresh() {
    const [transactionResponse, categoryResponse, ruleResponse] = await Promise.all([
      fetch(`${apiUrl}/v1/transactions?limit=100`, { headers }), fetch(`${apiUrl}/v1/categories`, { headers }), fetch(`${apiUrl}/v1/classification-rules`, { headers }),
    ]);
    if (!transactionResponse.ok || !categoryResponse.ok || !ruleResponse.ok) throw new Error("Start the local API to manage categories.");
    const [nextTransactions, nextCategories, nextRules] = await Promise.all([transactionResponse.json(), categoryResponse.json(), ruleResponse.json()]);
    setTransactions(nextTransactions); setCategories(nextCategories); setRules(nextRules); setStatus("Ready");
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(`${apiUrl}/v1/transactions?limit=100`, { headers }), fetch(`${apiUrl}/v1/categories`, { headers }), fetch(`${apiUrl}/v1/classification-rules`, { headers }),
    ]).then(async ([transactionResponse, categoryResponse, ruleResponse]) => {
      if (!transactionResponse.ok || !categoryResponse.ok || !ruleResponse.ok) throw new Error("Start the local API to manage categories.");
      const [nextTransactions, nextCategories, nextRules] = await Promise.all([transactionResponse.json(), categoryResponse.json(), ruleResponse.json()]);
      if (active) { setTransactions(nextTransactions); setCategories(nextCategories); setRules(nextRules); setStatus("Ready"); }
    }).catch((error) => { if (active) setStatus(error.message); });
    return () => { active = false; };
  }, []);
  const categoryById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);
  const children = useMemo(() => categories.filter((category) => category.parent_id), [categories]);
  const visibleTransactions = useMemo(() => transactions.filter((transaction) => transaction.description.toLowerCase().includes(query.toLowerCase())), [transactions, query]);

  async function categorize(event: FormEvent<HTMLFormElement>, transaction: Transaction) {
    event.preventDefault(); setSaving(transaction.id);
    const data = new FormData(event.currentTarget);
    const categoryId = data.get("category_id")?.toString();
    const response = await fetch(`${apiUrl}/v1/transactions/${transaction.id}/categorization`, { method: "PUT", headers, body: JSON.stringify({ allocations: [{ category_id: categoryId, amount: transaction.original_amount }], create_future_rule: data.get("future_rule") === "on" }) });
    setSaving(undefined);
    if (response.ok) { setStatus("Category saved. Historical records were not rewritten."); await refresh(); }
    else setStatus((await response.json()).detail ?? "Category could not be saved.");
  }

  async function addCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    const response = await fetch(`${apiUrl}/v1/categories`, { method: "POST", headers, body: JSON.stringify({ name: data.get("name"), parent_id: data.get("parent_id") || null }) });
    if (response.ok) { form.reset(); setStatus("Custom category created."); await refresh(); }
    else setStatus((await response.json()).detail ?? "Category could not be created.");
  }

  async function toggleRule(rule: Rule) {
    const response = await fetch(`${apiUrl}/v1/classification-rules/${rule.id}`, { method: "PUT", headers, body: JSON.stringify({ active: !rule.active }) });
    if (response.ok) { setStatus(rule.active ? "Rule disabled." : "Rule enabled."); await refresh(); }
  }

  async function deleteRule(rule: Rule) {
    if (!window.confirm(`Delete the private rule for ${rule.merchant_name ?? "this merchant"}?`)) return;
    const response = await fetch(`${apiUrl}/v1/classification-rules/${rule.id}`, { method: "DELETE", headers });
    if (response.ok) { setStatus("Rule deleted. Existing classifications were preserved."); await refresh(); }
  }

  function toggleSelected(id: string) {
    setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
    setBulkPreview(undefined);
  }

  async function previewBulk() {
    const response = await fetch(`${apiUrl}/v1/transactions/bulk-categorization/preview`, { method: "POST", headers, body: JSON.stringify({ transaction_ids: selected, category_id: bulkCategory }) });
    const body = await response.json();
    if (response.ok) { setBulkPreview(body); setStatus("Preview ready. Review totals before applying."); }
    else setStatus(body.detail ?? "Bulk preview could not be prepared.");
  }

  async function applyBulk() {
    const response = await fetch(`${apiUrl}/v1/transactions/bulk-categorization/apply`, { method: "POST", headers, body: JSON.stringify({ transaction_ids: selected, category_id: bulkCategory }) });
    const body = await response.json();
    if (response.ok) { setSelected([]); setBulkPreview(undefined); setBulkCategory(""); setStatus(`${body.updated} transactions categorized. No future merchant rule was created.`); await refresh(); }
    else setStatus(body.detail ?? "Bulk correction was not applied.");
  }

  const formatMoney = (value: string, currency: string) => new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-GB", { style: "currency", currency }).format(Number(value));

  return <main className="classification-shell" id="main-content">
    <header className="topbar"><Link className="brand" href="/"><span>EI</span>Expense Intelligence</Link><nav className="top-actions"><Link href="/imports">Import Statement</Link><Link href="/assistant">Assistant</Link><div className="environment"><i aria-hidden="true" /> Deterministic finance</div></nav></header>
    <section className="classification-hero"><div><p className="eyebrow">Transaction classification</p><h1>Put every expense in its place.</h1><p className="lede">Correct categories directly, preserve the original payment, and choose whether an exact merchant description should become your private future rule.</p></div><label>Search transactions<input name="search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} autoComplete="off" placeholder="Search by description…" /></label></section>
    <p className="status" role="status" aria-live="polite">{status}</p>
    <div className="classification-layout">
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">Ledger</p><h2>Review Categories</h2></div><span>{visibleTransactions.length} records</span></div>
        {selected.length ? <div className="bulk-bar"><div><strong>{selected.length} selected</strong><span>Bulk corrections never create merchant rules.</span></div><label>New category<select value={bulkCategory} onChange={(event) => { setBulkCategory(event.target.value); setBulkPreview(undefined); }}><option value="">Select a category…</option>{children.map((category) => <option key={category.id} value={category.id}>{categoryById.get(category.parent_id ?? "")?.name} — {category.name}</option>)}</select></label>{bulkPreview ? <button onClick={applyBulk}>Apply Confirmed Change</button> : <button disabled={!bulkCategory} onClick={previewBulk}>Preview Change</button>}{bulkPreview ? <small>{Object.entries(bulkPreview.totals_by_currency).map(([currency, amount]) => formatMoney(amount, currency)).join(" + ")} → {bulkPreview.category.name}</small> : null}</div> : null}
        {visibleTransactions.length ? <ul className="classification-list">{visibleTransactions.map((transaction) => <li key={transaction.id}>
          <label className="row-select"><input type="checkbox" checked={selected.includes(transaction.id)} onChange={() => toggleSelected(transaction.id)} /><span className="classification-copy"><strong>{transaction.description}</strong><span>{new Intl.DateTimeFormat(transaction.original_currency === "INR" ? "en-IN" : "en-GB", { dateStyle: "medium" }).format(new Date(`${transaction.effective_date}T00:00:00`))} · {transaction.classification_source.replaceAll("_", " ")}</span></span></label><b>{formatMoney(transaction.original_amount, transaction.original_currency)}</b>
          <form onSubmit={(event) => categorize(event, transaction)}><label>Category<select name="category_id" defaultValue="" required><option value="" disabled>Select a category…</option>{children.map((category) => <option key={category.id} value={category.id}>{categoryById.get(category.parent_id ?? "")?.name} — {category.name}</option>)}</select></label><label className="check"><input type="checkbox" name="future_rule" /> Apply to future exact matches</label><button disabled={saving === transaction.id} type="submit">{saving === transaction.id ? "Saving…" : "Save Category"}</button></form>
        </li>)}</ul> : <div className="empty"><h3>No matching transactions</h3><p>Try a different description.</p></div>}
      </section>
      <aside className="classification-side">
        <section className="panel"><p className="eyebrow">Your taxonomy</p><h2>Add a Custom Category</h2><form onSubmit={addCategory}><label>Name<input name="name" maxLength={100} required autoComplete="off" placeholder="e.g. Pet care…" /></label><label>Parent<select name="parent_id" required><option value="">Select a parent…</option>{categories.filter((category) => !category.parent_id).map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}</select></label><button type="submit">Create Category</button></form></section>
        <section className="panel"><p className="eyebrow">Private learning</p><h2>Exact-match Rules</h2>{rules.length ? <ul className="rule-list">{rules.map((rule) => <li key={rule.id}><div><strong>{rule.merchant_name ?? "Verified merchant"}</strong><span>{categoryById.get(rule.category_id)?.name ?? "Unavailable category"} · {rule.evidence_count} confirmation</span></div><div className="rule-actions"><button className="secondary" onClick={() => toggleRule(rule)}>{rule.active ? "Disable" : "Enable"}</button><button className="danger" onClick={() => deleteRule(rule)}>Delete</button></div></li>)}</ul> : <p className="rail-copy">No rules yet. Confirm “Apply to future exact matches” during a correction.</p>}</section>
      </aside>
    </div>
  </main>;
}
