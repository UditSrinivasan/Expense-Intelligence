"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type MoneyRow = { name: string; amount: number };
type Tutorial = {
  label: string; currency: string; subtotal: number; total: number; reconciled: boolean;
  participants: { name: string; paid: number; consumed: number; balance: number }[];
  components: { label: string; amount: number; rule: string; allocations: MoneyRow[] }[];
  settlements: { payer_name: string; payee_name: string; amount: number; currency: string; explanation: string }[];
};

export default function SplitTutorialPage() {
  const [data, setData] = useState<Tutorial | null>(null);
  const [status, setStatus] = useState("Loading the authoritative preview…");
  const [detail, setDetail] = useState(false);
  const money = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: data?.currency ?? "INR" }).format(value);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/backend/v1/tutorials/five-friends-split", { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error("The tutorial preview is unavailable.");
      return response.json() as Promise<Tutorial>;
    }).then(result => { setData(result); setStatus(""); }).catch(error => { if (error.name !== "AbortError") setStatus(error.message); });
    return () => controller.abort();
  }, []);
  const summary = data ? [
    "Five-friends dinner — tutorial only",
    `Total: ${money(data.total)}`,
    ...data.participants.map(person => `${person.name}: consumed ${money(person.consumed)}, paid ${money(person.paid)}`),
    ...data.settlements.map(row => `${row.payer_name} owes ${row.payee_name} ${money(row.amount)}`),
    ...(detail ? data.components.map(item => `${item.label} (${item.rule}): ${item.allocations.map(row => `${row.name} ${money(row.amount)}`).join(", ")}`) : []),
  ].join("\n") : "";
  async function copy() { if (!summary) return; await navigator.clipboard.writeText(summary); setStatus("Calculation copied. No private group details were included."); }
  async function share() {
    if (!summary) return;
    if (navigator.share) { try { await navigator.share({ title: "Expense split example", text: summary }); setStatus("Share sheet opened."); return; } catch (error) { if ((error as Error).name === "AbortError") return; } }
    await copy(); setStatus("Sharing is not available here, so the calculation was copied.");
  }
  return <main id="main-content" className="tutorial-page">
    <header className="tutorial-heading"><div><p className="eyebrow">Interactive walkthrough</p><h1>Five friends. One exact bill.</h1><p className="lede">A non-persistent example using the same allocation and settlement logic as real group expenses.</p></div><span className="tutorial-badge">Never saved to your ledger</span></header>
    {status ? <p className="status" role="status" aria-live="polite">{status}</p> : null}
    {data ? <>
      <section className="panel tutorial-story" data-tour="tutorial-split"><div><p className="eyebrow">The bill</p><h2>{money(data.total)}</h2><p>Two people pay. Each item goes only to the people who consumed it. Non-drinkers never receive wine charges.</p></div><dl><div><dt>Items</dt><dd>{money(data.subtotal)}</dd></div><div><dt>Service, tax & discount</dt><dd>{money(data.total - data.subtotal)}</dd></div><div><dt>Reconciliation</dt><dd className={data.reconciled ? "verified-line" : "validation-error"}>{data.reconciled ? "Exact" : "Check required"}</dd></div></dl></section>
      <section className="tutorial-grid">
        <div className="panel"><p className="eyebrow">1 · Consumption</p><h2>Item assignments</h2><p className="context-help">Shared items split only among selected diners. Tax, service, and discounts follow the visible consumption-weighted rule.</p>{data.components.map(component => <details className="tutorial-component" key={component.label}><summary><span>{component.label}</span><strong>{money(component.amount)}</strong></summary><p>{component.rule}</p><ul>{component.allocations.map(row => <li key={row.name}><span>{row.name}</span><b>{money(row.amount)}</b></li>)}</ul></details>)}</div>
        <div className="panel" data-tour="tutorial-balances"><p className="eyebrow">2 · Paid versus owed</p><h2>Individual totals</h2><p className="context-help"><strong>Paid</strong> is money put toward the bill. <strong>Consumed</strong> is the assigned share. Their difference creates the balance—payment can exceed personal consumption.</p><div className="tutorial-table" role="table" aria-label="Participant balances"><div role="row"><b role="columnheader">Person</b><b role="columnheader">Paid</b><b role="columnheader">Consumed</b><b role="columnheader">Balance</b></div>{data.participants.map(person => <div role="row" key={person.name}><span role="cell">{person.name}</span><span role="cell">{money(person.paid)}</span><span role="cell">{money(person.consumed)}</span><strong role="cell">{money(person.balance)}</strong></div>)}</div></div>
      </section>
      <section className="panel tutorial-settlements" data-tour="tutorial-settlements"><div><p className="eyebrow">3 · Suggested repayments</p><h2>Who owes whom</h2><p className="context-help">Suggestions preserve everyone’s net balance. They do not mean anyone has settled until a payment is explicitly recorded.</p></div><ul>{data.settlements.map(row => <li key={`${row.payer_name}-${row.payee_name}`}><span><strong>{row.payer_name}</strong> pays {row.payee_name}</span><b>{money(row.amount)}</b></li>)}</ul><div className="share-actions"><label className="check"><input type="checkbox" checked={detail} onChange={event => setDetail(event.target.checked)}/>Include item details</label><button onClick={() => void copy()}>Copy calculation</button><button className="primary-button" onClick={() => void share()}>Share example</button></div><Feedback kind="split" /></section>
      <nav className="tutorial-next" aria-label="Tutorial next actions"><Link href="/groups">Return to your groups</Link><Link className="primary-link" href="/groups">Create a real group</Link></nav>
    </> : null}
  </main>;
}

function Feedback({ kind }: { kind: "split" }) {
  const [message, setMessage] = useState("");
  async function send() {
    const response = await fetch("/api/backend/v1/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, sentiment: "confusing", reason: "hard_to_understand" }) });
    setMessage(response.ok ? "Thanks—your feedback was recorded. It does not automatically retrain a model." : "Feedback could not be recorded.");
  }
  return <div className="inline-feedback"><button className="text-button" onClick={() => void send()}>This calculation is confusing</button><span role="status">{message}</span></div>;
}
