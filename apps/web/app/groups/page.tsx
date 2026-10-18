"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Member = {
  id: string;
  display_name: string;
  role: string;
  is_guest: boolean;
};
type Group = {
  id: string;
  name: string;
  default_currency: string;
  version: number;
  archived: boolean;
  current_user_role: string;
  last_activity_at: string | null;
  outstanding_by_currency: Record<string, string>;
  members: Member[];
};

const headers = { "Content-Type": "application/json" };

export default function GroupsDirectoryPage() {
  const [groups, setGroups] = useState<Group[]>([]);
  const [status, setStatus] = useState("Loading your groups…");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const response = await fetch(
      "/api/backend/v1/groups?include_archived=true",
      { headers },
    );
    if (!response.ok)
      throw new Error("Groups could not be loaded. Refresh and try again.");
    const next = (await response.json()) as Group[];
    setGroups(next);
    setStatus(
      next.length
        ? `${next.filter((group) => !group.archived).length} active group${next.filter((group) => !group.archived).length === 1 ? "" : "s"}`
        : "Create a group for a trip, home, or recurring shared expense.",
    );
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/backend/v1/groups?include_archived=true", { headers })
      .then(async (response) => {
        if (!response.ok)
          throw new Error("Groups could not be loaded. Refresh and try again.");
        const next = (await response.json()) as Group[];
        if (active) {
          setGroups(next);
          setStatus(
            next.length
              ? `${next.filter((group) => !group.archived).length} active group${next.filter((group) => !group.archived).length === 1 ? "" : "s"}`
              : "Create a group for a trip, home, or recurring shared expense.",
          );
        }
      })
      .catch((error: Error) => {
        if (active) setStatus(error.message);
      });
    return () => {
      active = false;
    };
  }, []);

  async function createGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = event.currentTarget;
    const data = new FormData(form);
    const response = await fetch("/api/backend/v1/groups", {
      method: "POST",
      headers,
      body: JSON.stringify({
        name: data.get("name"),
        owner_name: data.get("owner_name"),
        default_currency: data.get("currency"),
      }),
    });
    const result = await response.json();
    setBusy(false);
    if (!response.ok)
      return setStatus(result.detail ?? "Group could not be created.");
    form.reset();
    await load();
    setStatus(`${result.name} is ready. Add people from its workspace.`);
  }

  const active = useMemo(
    () => groups.filter((group) => !group.archived),
    [groups],
  );
  const archived = useMemo(
    () => groups.filter((group) => group.archived),
    [groups],
  );
  return (
    <main className="groups-directory" id="main-content">
      <section className="directory-heading">
        <div>
          <p className="eyebrow">Shared money</p>
          <h1>Your Groups</h1>
          <p className="lede">
            Keep each household, trip, and shared plan separate. Open a
            workspace to see expenses, balances, settlements, and members.
          </p>
        </div>
        <details className="create-group-panel">
          <summary className="primary-button">Create Group</summary>
          <form onSubmit={createGroup}>
            <label>
              Group name
              <input
                name="name"
                required
                maxLength={120}
                autoComplete="off"
                placeholder="Weekend away…"
              />
            </label>
            <label>
              Your display name
              <input
                name="owner_name"
                required
                maxLength={120}
                autoComplete="name"
                placeholder="Asha…"
              />
            </label>
            <label>
              Default currency
              <select name="currency" defaultValue="INR">
                <option>INR</option>
                <option>GBP</option>
                <option>USD</option>
                <option>EUR</option>
                <option>JPY</option>
                <option>KWD</option>
              </select>
            </label>
            <button disabled={busy}>
              {busy ? "Creating…" : "Create Group"}
            </button>
          </form>
        </details>
      </section>
      <p className="status" role="status" aria-live="polite">
        {status}
      </p>
      {active.length ? (
        <section aria-labelledby="active-groups">
          <div className="directory-section-heading">
            <div>
              <p className="eyebrow">Active</p>
              <h2 id="active-groups">Groups You Share</h2>
            </div>
            <Link href="/groups/new-expense" className="text-link">
              Split a new bill
            </Link>
          </div>
          <div className="group-card-grid">
            {active.map((group) => (
              <GroupCard group={group} key={group.id} />
            ))}
          </div>
        </section>
      ) : (
        <section className="panel directory-empty">
          <span aria-hidden="true">GR</span>
          <h2>No groups yet</h2>
          <p>
            Create a group for flatmates, a holiday, or a dinner. Nothing is
            added to your ledger until you confirm an expense.
          </p>
        </section>
      )}
      {archived.length ? (
        <details className="archived-groups">
          <summary>
            {archived.length} archived group{archived.length === 1 ? "" : "s"}
          </summary>
          <div className="group-card-grid">
            {archived.map((group) => (
              <GroupCard group={group} key={group.id} />
            ))}
          </div>
        </details>
      ) : null}
    </main>
  );
}

function GroupCard({ group }: { group: Group }) {
  const outstanding = Object.entries(group.outstanding_by_currency ?? {});
  const lastActivity = group.last_activity_at
    ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
        new Date(group.last_activity_at),
      )
    : "No expenses yet";
  return (
    <article
      className={`group-directory-card${group.archived ? " archived" : ""}`}
    >
      <div className="group-card-top">
        <span className="group-monogram" aria-hidden="true">
          {group.name.slice(0, 2).toUpperCase()}
        </span>
        <span className="group-state">
          {group.archived ? "Archived" : (group.current_user_role ?? "Member")}
        </span>
      </div>
      <div>
        <h3>{group.name}</h3>
        <p>
          {group.members.length} member{group.members.length === 1 ? "" : "s"} ·{" "}
          {group.default_currency} default
        </p>
      </div>
      <dl>
        <div>
          <dt>Outstanding</dt>
          <dd>
            {outstanding.length
              ? outstanding
                  .map(([currency, amount]) =>
                    new Intl.NumberFormat(undefined, {
                      style: "currency",
                      currency,
                    }).format(Number(amount)),
                  )
                  .join(" · ")
              : "All settled"}
          </dd>
        </div>
        <div>
          <dt>Recent activity</dt>
          <dd>{lastActivity}</dd>
        </div>
      </dl>
      <div className="group-card-actions">
        <Link className="primary-link" href={`/groups/${group.id}`}>
          {group.archived ? "View & Restore" : "Open Group"}
        </Link>
        {group.archived ? null : (
          <Link href={`/groups/new-expense?group=${group.id}`}>Add Expense</Link>
        )}
      </div>
    </article>
  );
}
