"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Analytics, Balance, ExpensesPanel, GroupSettingsPanel, HistoryPanel, Member, MembersPanel, OverviewPanel, Settlement, SettlePanel, Suggestion, Template, TemplatesPanel } from "./group-panels";

type Group = { id: string; name: string; default_currency: string; version: number; archived: boolean; current_user_role: string };
type Tab = "overview" | "expenses" | "settle" | "templates" | "history" | "members" | "settings";
const tabs: { id: Tab; label: string }[] = [{ id: "overview", label: "Overview" }, { id: "expenses", label: "Expenses" }, { id: "settle", label: "Balances & Settle" }, { id: "templates", label: "Templates" }, { id: "history", label: "History" }, { id: "members", label: "Members" }, { id: "settings", label: "Settings" }];
const apiUrl = "/api/backend";
const headers = { "Content-Type": "application/json" };

async function fetchWorkspace(id: string) {
  const responses = await Promise.all([fetch(`${apiUrl}/v1/groups/${id}`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/members/all`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/balances`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/debt-suggestions`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/settlements`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/templates?include_archived=true`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/analytics`, { headers }), fetch(`${apiUrl}/v1/groups/${id}/activity`, { headers })]);
  if (responses.some((response) => !response.ok)) throw new Error("This group workspace could not be loaded.");
  return Promise.all(responses.map((response) => response.json()));
}

export default function GroupWorkspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const initialTab = tabs.some((item) => item.id === requestedTab) ? requestedTab as Tab : "overview";
  const [selectedTab, setSelectedTab] = useState<Tab>();
  const tab = selectedTab ?? initialTab;
  const [group, setGroup] = useState<Group>();
  const [members, setMembers] = useState<Member[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [settlements, setSettlements] = useState<Settlement[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [analytics, setAnalytics] = useState<Analytics>();
  const [activity, setActivity] = useState<Activity>({ expenses: [], settlements: [] });
  const [status, setStatus] = useState("Loading group workspace…");
  const assign = useCallback(([nextGroup, nextMembers, nextBalances, debts, nextSettlements, nextTemplates, nextAnalytics, nextActivity]: Awaited<ReturnType<typeof fetchWorkspace>>) => { setGroup(nextGroup); setMembers(nextMembers); setBalances(nextBalances); setSuggestions(debts.suggestions); setSettlements(nextSettlements); setTemplates(nextTemplates); setAnalytics(nextAnalytics); setActivity(nextActivity); setStatus(nextGroup.archived ? "This group is archived. Its financial history remains available." : "Original-currency obligations remain separate and auditable."); }, []);
  const load = useCallback(async () => assign(await fetchWorkspace(id)), [assign, id]);
  useEffect(() => { let active = true; fetchWorkspace(id).then((data) => { if (active) assign(data); }).catch((error) => { if (active) setStatus(error.message); }); return () => { active = false; }; }, [assign, id]);

  async function mutate(path: string, method: string, body?: object) {
    const response = await fetch(`${apiUrl}/v1/groups/${id}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const result = await response.json();
    if (!response.ok) { setStatus(result.detail ?? "The change could not be saved."); return undefined; }
    await load(); return result;
  }
  function selectTab(next: Tab) {
    setSelectedTab(next);
    window.history.replaceState(null, "", next === "overview" ? window.location.pathname : `${window.location.pathname}?tab=${next}`);
  }
  const names = useMemo(() => new Map(members.map((member) => [member.id, member.display_name])), [members]);
  return <main className="group-workspace" id="main-content">
    <Link className="back-link" href="/groups">← Back to Groups</Link>
    <section className="workspace-heading"><div><p className="eyebrow">Group workspace</p><h1>{group?.name ?? "Shared Finances"}</h1><p className="lede">Track what was spent, what each person consumed, and what remains to settle.</p></div><div className="workspace-actions">{group ? <span className="currency-badge">{group.default_currency} default · version {group.version}</span> : null}{group && !group.archived ? <Link className="primary-link" href={`/groups/new-expense?group=${id}`}>Add Expense</Link> : null}</div></section>
    <p className="status" role="status" aria-live="polite">{status}</p>
    <nav className="workspace-tabs" aria-label="Group sections">{tabs.map((item) => <button className={tab === item.id ? "active" : ""} aria-current={tab === item.id ? "page" : undefined} key={item.id} onClick={() => selectTab(item.id)}>{item.label}</button>)}</nav>
    <section className="panel workspace-panel">{group && analytics ? <>
      {tab === "overview" ? <OverviewPanel groupId={id} analytics={analytics} balances={balances} suggestions={suggestions}/> : null}
      {tab === "expenses" ? <ExpensesPanel groupId={id} expenses={analytics.recent_expenses}/> : null}
      {tab === "settle" ? <SettlePanel groupId={id} expenses={analytics.recent_expenses} suggestions={suggestions} settlements={settlements} version={group.version} names={names} submit={(body) => mutate("/settlements", "POST", body).then(() => undefined)} confirm={(settlementId) => mutate(`/settlements/${settlementId}/confirm?expected_group_version=${group.version}`, "POST").then(() => undefined)} reverse={(settlementId, reference) => mutate(`/settlements/${settlementId}/reverse`, "POST", { idempotency_key: crypto.randomUUID(), expected_group_version: group.version, reference }).then(() => undefined)}/> : null}
      {tab === "templates" ? <TemplatesPanel templates={templates} members={members} currency={group.default_currency} create={(body) => mutate("/templates", "POST", body).then(() => undefined)} update={(templateId, body) => mutate(`/templates/${templateId}`, "PUT", body).then(() => undefined)} setActive={(templateId, version, active) => mutate(`/templates/${templateId}/status`, "PATCH", { expected_version: version, active }).then(() => undefined)} apply={async (templateId) => { const draft = await mutate(`/templates/${templateId}/apply`, "POST"); if (draft) { sessionStorage.setItem("expense-intelligence-template-draft", JSON.stringify({ group_id: id, ...draft })); router.push("/groups/new-expense"); } }}/> : null}
      {tab === "history" ? <HistoryPanel groupId={id} activity={activity} names={names}/> : null}
      {tab === "members" ? <MembersPanel members={members} version={group.version} canManage={group.current_user_role === "owner"} add={(body) => mutate("/members", "POST", body).then(() => undefined)} update={(memberId, body) => mutate(`/members/${memberId}`, "PUT", body).then(() => undefined)}/> : null}
      {tab === "settings" ? <GroupSettingsPanel group={group} update={(body) => mutate("", "PUT", body).then(() => undefined)}/> : null}
    </> : <div className="empty"><span>…</span><h3>Loading group intelligence</h3></div>}</section>
  </main>;
}
