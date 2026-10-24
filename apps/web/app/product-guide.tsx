"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

type ChecklistItem = { key: string; label: string; href: string; completed: boolean };
type Experience = { tour_state: "never_started" | "in_progress" | "completed" | "skipped"; tour_step: number; checklist_dismissed: boolean; checklist: ChecklistItem[] };
type Step = { section: string; title: string; body: string; href: string; target: string };

const steps: Step[] = [
  { section: "Managing personal finances", title: "Your financial overview", body: "See cash flow and personal consumption separately, with currencies kept distinct.", href: "/", target: "nav-ov" },
  { section: "Managing personal finances", title: "Add expenses and income", body: "Record a purchase, refund, transfer, or income. Every amount remains traceable to its source.", href: "/transactions?add=true", target: "nav-tr" },
  { section: "Importing and categorizing", title: "Import statements", body: "Map a CSV or spreadsheet, review every row, then confirm the batch atomically.", href: "/imports", target: "nav-im" },
  { section: "Importing and categorizing", title: "Scan receipts and PDFs", body: "Documents stay in your browser while text is extracted. Correct the preview before saving.", href: "/documents", target: "nav-im" },
  { section: "Importing and categorizing", title: "Categories that learn", body: "Corrections can create a merchant rule for future transactions. A suggestion never silently changes your ledger.", href: "/transactions", target: "nav-tr" },
  { section: "Budgets and insights", title: "Plan with budgets", body: "Budgets compare your consumption with a limit; cash outflow can differ when someone else owes you.", href: "/budgets", target: "nav-bu" },
  { section: "Budgets and insights", title: "Understand unusual activity", body: "Alerts link to supporting transactions and are evidence-based signals—not financial advice.", href: "/#insights", target: "nav-in" },
  { section: "Groups and expense splitting", title: "Keep groups separate", body: "Create distinct workspaces for trips, homes, or friends. Only members can access group records.", href: "/groups", target: "nav-gr" },
  { section: "Groups and expense splitting", title: "Try the five-friends dinner", body: "Walk through item assignment, two payers, exclusions, proportional charges, exact balances, and sharing—without saving tutorial data.", href: "/groups/tutorial", target: "tutorial-split" },
  { section: "Groups and expense splitting", title: "Who paid is not who consumed", body: "Payers fund the bill; allocations record consumption; balances show who owes; settlements record money actually returned.", href: "/groups/tutorial", target: "tutorial-balances" },
  { section: "Groups and expense splitting", title: "Settlements and sharing", body: "Suggestions simplify net balances but never record payment. Confirm settlements yourself, then copy a backend-reconciled summary.", href: "/groups/tutorial", target: "tutorial-settlements" },
  { section: "Assistant and settings", title: "Ask the finance assistant", body: "The lab shows tool activity and evidence. It is currently disconnected from private ledgers and external models.", href: "/assistant", target: "nav-ai" },
  { section: "Assistant and settings", title: "Privacy and preferences", body: "Control regional formatting, review memory status, replay this tour, or sign out from Settings.", href: "/settings", target: "nav-se" },
];

async function save(update: Record<string, unknown>) {
  const response = await fetch("/api/backend/v1/experience", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(update) });
  if (!response.ok) throw new Error("Your tour progress could not be saved.");
  return response.json() as Promise<Experience>;
}

export function ProductGuide({ pathname }: { pathname: string }) {
  const router = useRouter();
  const [experience, setExperience] = useState<Experience | null>(null);
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const panelRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/backend/v1/experience", { signal: controller.signal }).then(response => response.ok ? response.json() : null).then((data: Experience | null) => {
      if (!data?.checklist || !Array.isArray(data.checklist)) return;
      setExperience(data);
      setOpen(data.tour_state === "never_started" || data.tour_state === "in_progress");
    }).catch(() => undefined);
    return () => controller.abort();
  }, []);

  const index = Math.min(experience?.tour_step ?? 0, steps.length - 1);
  const step = steps[index];
  const sectionEnd = useMemo(() => steps.findIndex((item, itemIndex) => itemIndex > index && item.section !== step.section), [index, step.section]);
  useEffect(() => {
    document.querySelectorAll(".tour-highlight").forEach(node => node.classList.remove("tour-highlight"));
    if (!open || experience?.tour_state !== "in_progress") return;
    let attempts = 0;
    const timer = window.setInterval(() => {
      const target = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
      attempts += 1;
      if (target) { target.classList.add("tour-highlight"); target.scrollIntoView({ block: "nearest" }); window.clearInterval(timer); }
      if (attempts > 15) window.clearInterval(timer);
    }, 100);
    return () => { window.clearInterval(timer); document.querySelectorAll(".tour-highlight").forEach(node => node.classList.remove("tour-highlight")); };
  }, [experience?.tour_state, open, pathname, step.target]);

  async function update(values: Record<string, unknown>) {
    try { const data = await save(values); setExperience(data); setNotice(""); return data; }
    catch (error) { setNotice(error instanceof Error ? error.message : "Progress could not be saved."); }
  }
  async function start() { await update({ tour_state: "in_progress", tour_step: 0 }); setOpen(true); router.push(steps[0].href); }
  async function move(next: number) {
    if (next >= steps.length) { await update({ tour_state: "completed", tour_step: steps.length - 1 }); setOpen(false); return; }
    await update({ tour_state: "in_progress", tour_step: next }); router.push(steps[next].href);
  }
  if (!experience) return null;
  const welcome = experience.tour_state === "never_started";
  const done = experience.checklist.filter(item => item.completed).length;
  return <>
    {pathname === "/" && !open && !experience.checklist_dismissed && done < experience.checklist.length ? <aside className="onboarding-checklist" aria-labelledby="checklist-title">
      <div><p className="eyebrow">Getting started</p><h2 id="checklist-title">Your checklist</h2><p>{done} of {experience.checklist.length} complete. These update from real saved actions.</p></div>
      <ol>{experience.checklist.map(item => <li className={item.completed ? "complete" : ""} key={item.key}><span aria-hidden="true">{item.completed ? "✓" : "○"}</span><Link href={item.href}>{item.label}</Link>{item.key === "dashboard" && !item.completed ? <button onClick={() => void update({ dashboard_reviewed: true })}>Mark reviewed</button> : null}</li>)}</ol>
      <button className="text-button" onClick={() => void update({ checklist_dismissed: true })}>Dismiss checklist</button>
    </aside> : null}
    {pathname === "/settings" && !open ? <button className="replay-tour" onClick={() => void start()}>Replay product tour</button> : null}
    {open ? <aside className="product-tour" ref={panelRef} aria-labelledby="tour-title" aria-live="polite">
      {welcome ? <><p className="eyebrow">Welcome</p><h2 id="tour-title">Welcome to Expense Intelligence</h2><p>Understand personal spending, plan budgets, and settle shared expenses from records you can verify.</p><div className="tour-actions"><button className="primary-button" onClick={() => void start()}>Start tour</button><button onClick={() => { void update({ tour_state: "skipped", tour_step: 0 }); setOpen(false); }}>Skip tour</button></div></> : <>
        <div className="tour-progress"><span>{step.section}</span><span>Step {index + 1} of {steps.length}</span></div>
        <progress value={index + 1} max={steps.length}>Step {index + 1} of {steps.length}</progress>
        <h2 id="tour-title">{step.title}</h2><p>{step.body}</p>
        {!((step.href.startsWith("/#") && pathname === "/") || pathname === step.href.split("?")[0].split("#")[0] || (step.href !== "/" && pathname.startsWith(`${step.href.split("?")[0].split("#")[0]}/`))) ? <Link className="tour-route" href={step.href}>Open this area</Link> : null}
        <div className="tour-actions"><button disabled={index === 0} onClick={() => void move(index - 1)}>Previous</button><button className="primary-button" onClick={() => void move(index + 1)}>{index === steps.length - 1 ? "Finish" : "Next"}</button></div>
        <div className="tour-minor-actions">{sectionEnd > 0 ? <button onClick={() => void move(sectionEnd)}>Skip section</button> : null}<button onClick={() => { void update({ tour_state: "skipped", tour_step: index }); setOpen(false); }}>Exit tour</button></div>
      </>}
      {notice ? <p className="status error" role="alert">{notice}</p> : null}
    </aside> : null}
  </>;
}
