"use client";
import { FormEvent } from "react";
import Link from "next/link";
export type Member = {
  id: string;
  display_name: string;
  role: string;
  active: boolean;
  is_guest: boolean;
};
export type Balance = {
  member_id: string;
  display_name: string;
  active: boolean;
  currency: string;
  paid: string;
  owed: string;
  settled_out: string;
  settled_in: string;
  balance: string;
};
export type Suggestion = {
  payer_member_id: string;
  payer_name: string;
  payee_member_id: string;
  payee_name: string;
  amount: string;
  currency: string;
  explanation: string;
};
export type Settlement = {
  id: string;
  payer_member_id: string;
  payee_member_id: string;
  amount: string;
  currency: string;
  settlement_date: string;
  reference: string | null;
  status: string;
  kind: string;
};
export type Template = {
  id: string;
  name: string;
  description: string;
  currency: string;
  version: number;
  components: {
    label: string;
    amount: string;
    strategy: string;
  }[];
};
export type Analytics = {
  totals_by_currency: Record<string, string>;
  spending_by_category: Record<string, Record<string, string>>;
  spending_over_time: Record<string, Record<string, string>>;
  settlements_completed: number;
  recent_expenses: {
    id: string;
    description: string;
    total: string;
    currency: string;
    expense_date: string;
  }[];
  largest_expenses: {
    id: string;
    description: string;
    total: string;
    currency: string;
  }[];
  currency_policy: string;
};
const money = (amount: string, currency: string) =>
  new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-GB", {
    style: "currency",
    currency,
  }).format(Number(amount));
export function OverviewPanel({
  groupId,
  analytics,
  balances,
  suggestions,
}: {
  groupId: string;
  analytics: Analytics;
  balances: Balance[];
  suggestions: Suggestion[];
}) {
  return (
    <div className="group-dashboard">
      <section className="group-metrics">
        {Object.entries(analytics.totals_by_currency).map(
          ([currency, total]) => (
            <article key={currency}>
              <span>Total shared spend · {currency}</span>
              <strong>{money(total, currency)}</strong>
            </article>
          ),
        )}
        <article>
          <span>Settlements completed</span>
          <strong>{analytics.settlements_completed}</strong>
        </article>
        <article>
          <span>Open transfers</span>
          <strong>{suggestions.length}</strong>
        </article>
      </section>
      <div className="group-data-grid">
        <section>
          <h3>Outstanding balances</h3>
          {balances.length ? (
            balances.map((row) => (
              <div
                className="finance-row"
                key={`${row.member_id}-${row.currency}`}
              >
                <span>
                  {row.display_name}
                  {row.active ? "" : " · former"}
                  <small>
                    {money(row.paid, row.currency)} paid ·{" "}
                    {money(row.owed, row.currency)} consumed
                  </small>
                </span>
                <b className={Number(row.balance) < 0 ? "negative" : ""}>
                  {money(row.balance, row.currency)}
                </b>
              </div>
            ))
          ) : (
            <p className="muted">No balances yet.</p>
          )}
        </section>
        <section>
          <h3>Recent expenses</h3>
          {analytics.recent_expenses.map((expense) => (
            <Link
              className="finance-row expense-link"
              href={`/groups/${groupId}/expenses/${expense.id}`}
              key={expense.id}
            >
              <span>
                {expense.description}
                <small>
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeZone: "UTC",
                  }).format(new Date(`${expense.expense_date}T00:00:00Z`))}
                </small>
              </span>
              <b>{money(expense.total, expense.currency)}</b>
            </Link>
          ))}
        </section>
        <section>
          <h3>Spending by category</h3>
          {Object.entries(analytics.spending_by_category).flatMap(
            ([category, totals]) =>
              Object.entries(totals).map(([currency, total]) => (
                <div className="finance-row" key={`${category}-${currency}`}>
                  <span>
                    {category === "uncategorized" ? "Uncategorized" : category}
                  </span>
                  <b>{money(total, currency)}</b>
                </div>
              )),
          )}
        </section>
        <section>
          <h3>Spending over time</h3>
          {Object.entries(analytics.spending_over_time).flatMap(
            ([day, totals]) =>
              Object.entries(totals).map(([currency, total]) => (
                <div className="finance-row" key={`${day}-${currency}`}>
                  <span>{day}</span>
                  <b>{money(total, currency)}</b>
                </div>
              )),
          )}
        </section>
        <section>
          <h3>Largest expenses</h3>
          {analytics.largest_expenses.map((expense) => (
            <div className="finance-row" key={expense.id}>
              <span>{expense.description}</span>
              <b>{money(expense.total, expense.currency)}</b>
            </div>
          ))}
        </section>
      </div>
      <p className="finance-policy">{analytics.currency_policy}</p>
    </div>
  );
}

export function ExpensesPanel({
  groupId,
  expenses,
}: {
  groupId: string;
  expenses: Analytics["recent_expenses"];
}) {
  return (
    <section>
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Confirmed history</p>
          <h2>Group Expenses</h2>
        </div>
        <Link className="primary-link" href={`/groups/new-expense?group=${groupId}`}>
          Add Expense
        </Link>
      </div>
      {expenses.length ? (
        <div className="expense-directory-list">
          {expenses.map((expense) => (
            <Link
              className="finance-row expense-link"
              href={`/groups/${groupId}/expenses/${expense.id}`}
              key={expense.id}
            >
              <span>
                <strong>{expense.description}</strong>
                <small>
                  {new Intl.DateTimeFormat(undefined, {
                    dateStyle: "medium",
                    timeZone: "UTC",
                  }).format(new Date(`${expense.expense_date}T00:00:00Z`))}{" "}
                  · View calculation & sharing
                </small>
              </span>
              <b>{money(expense.total, expense.currency)}</b>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty compact">
          <h3>No confirmed expenses</h3>
          <p>Add a bill when this group is ready.</p>
        </div>
      )}
    </section>
  );
}
export function SettlePanel({
  groupId,
  expenses,
  suggestions,
  settlements,
  version,
  names,
  submit,
}: {
  groupId: string;
  expenses: Analytics["recent_expenses"];
  suggestions: Suggestion[];
  settlements: Settlement[];
  version: number;
  names: Map<string, string>;
  submit: (body: object) => Promise<void>;
}) {
  async function settle(
    event: FormEvent<HTMLFormElement>,
    suggestion: Suggestion,
  ) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await submit({
      idempotency_key: crypto.randomUUID(),
      expected_group_version: version,
      payer_member_id: suggestion.payer_member_id,
      payee_member_id: suggestion.payee_member_id,
      amount: data.get("amount"),
      currency: suggestion.currency,
      settlement_date: data.get("date"),
      reference: data.get("reference"),
      status: data.get("status"),
    });
  }
  return (
    <div className="group-data-grid">
      <section>
        <h3>Suggested transfers</h3>
        <p className="muted">
          Greedy net-balance matching preserves balances; suggestions do not
          record payment.
        </p>
        {suggestions.map((item) => (
          <form
            className="settlement-card"
            key={`${item.payer_member_id}-${item.payee_member_id}-${item.currency}`}
            onSubmit={(event) => settle(event, item)}
          >
            <strong>
              {item.payer_name} → {item.payee_name}
            </strong>
            <span>{money(item.amount, item.currency)}</span>
            <div className="form-row">
              <label>
                Amount
                <input
                  name="amount"
                  required
                  defaultValue={item.amount}
                  inputMode="decimal"
                />
              </label>
              <label>
                Date
                <input
                  name="date"
                  type="date"
                  required
                  defaultValue={new Date().toISOString().slice(0, 10)}
                />
              </label>
            </div>
            <label>
              Reference
              <input
                name="reference"
                maxLength={160}
                placeholder="Bank or cash note"
              />
            </label>
            <label>
              State
              <select name="status">
                <option value="confirmed">Completed externally</option>
                <option value="pending">Pending agreement</option>
              </select>
            </label>
            <button>Record Settlement</button>
          </form>
        ))}
      </section>
      <section>
        <h3>Settlement history</h3>
        {settlements.length ? (
          settlements.map((row) => (
            <div className="finance-row" key={row.id}>
              <span>
                {names.get(row.payer_member_id)} →{" "}
                {names.get(row.payee_member_id)}
                <small>
                  {row.settlement_date} · {row.kind} · {row.status}
                  {row.reference ? ` · ${row.reference}` : ""}
                </small>
              </span>
              <b>{money(row.amount, row.currency)}</b>
            </div>
          ))
        ) : (
          <p className="muted">No repayments recorded.</p>
        )}
        <h3>Expense calculations</h3>
        {expenses.map((expense) => (
          <Link
            className="finance-row expense-link"
            href={`/groups/${groupId}/expenses/${expense.id}`}
            key={expense.id}
          >
            <span>
              {expense.description}
              <small>Copy or share confirmed calculation</small>
            </span>
            <b>{money(expense.total, expense.currency)}</b>
          </Link>
        ))}
      </section>
    </div>
  );
}
export function TemplatesPanel({
  templates,
  members,
  currency,
  create,
  apply,
}: {
  templates: Template[];
  members: Member[];
  currency: string;
  create: (body: object) => Promise<void>;
  apply: (id: string) => Promise<void>;
}) {
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await create({
      name: data.get("name"),
      description: data.get("description"),
      currency: data.get("currency"),
      components: [
        {
          label: data.get("label"),
          amount: data.get("amount"),
          strategy: "equal",
          shares: members
            .filter((member) => member.active)
            .map((member) => ({ member_id: member.id })),
        },
      ],
    });
    form.reset();
  }
  return (
    <div className="group-data-grid">
      <section>
        <h3>Reusable templates</h3>
        {templates.length ? (
          templates.map((row) => (
            <div className="template-card" key={row.id}>
              <div>
                <strong>{row.name}</strong>
                <span>
                  {row.description} · v{row.version}
                </span>
              </div>
              <button className="secondary" onClick={() => apply(row.id)}>
                Prepare Draft
              </button>
            </div>
          ))
        ) : (
          <p className="muted">No templates yet.</p>
        )}
      </section>
      <section>
        <h3>New equal-split template</h3>
        <form onSubmit={save}>
          <label>
            Name
            <input
              name="name"
              required
              maxLength={120}
              placeholder="Monthly internet"
            />
          </label>
          <label>
            Expense description
            <input name="description" required maxLength={280} />
          </label>
          <div className="form-row">
            <label>
              Component
              <input name="label" required defaultValue="Shared charge" />
            </label>
            <label>
              Default amount
              <input name="amount" required inputMode="decimal" />
            </label>
          </div>
          <label>
            Currency
            <select name="currency" defaultValue={currency}>
              <option>INR</option>
              <option>GBP</option>
              <option>USD</option>
              <option>EUR</option>
              <option>JPY</option>
              <option>KWD</option>
            </select>
          </label>
          <button>Save Template</button>
        </form>
      </section>
    </div>
  );
}
export function MembersPanel({
  members,
  version,
  canManage,
  add,
  update,
}: {
  members: Member[];
  version: number;
  canManage: boolean;
  add: (body: object) => Promise<void>;
  update: (id: string, body: object) => Promise<void>;
}) {
  async function addGuest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await add({ display_name: data.get("display_name") });
    form.reset();
  }
  return (
    <section>
      <div className="panel-title-row">
        <div>
          <p className="eyebrow">Participation</p>
          <h2>Members</h2>
        </div>
        <span>{members.filter((member) => member.active).length} active</span>
      </div>
      <p className="muted">
        Former members retain their financial history and balances.
        Registered-user invitations remain disabled until secure acceptance is
        configured.
      </p>
      {canManage ? (
        <form className="inline-add-member" onSubmit={addGuest}>
          <label>
            Guest name
            <input
              name="display_name"
              required
              maxLength={120}
              autoComplete="off"
              placeholder="Add someone…"
            />
          </label>
          <button>Add Guest</button>
        </form>
      ) : null}
      {members.map((member) => (
        <form
          className="member-manage"
          key={member.id}
          onSubmit={(event) => {
            event.preventDefault();
            const data = new FormData(event.currentTarget);
            update(member.id, {
              expected_group_version: version,
              display_name: data.get("display_name"),
              active: data.get("active") === "true",
            });
          }}
        >
          <label>
            Name
            <input
              name="display_name"
              defaultValue={member.display_name}
              required
              disabled={!canManage}
            />
          </label>
          <label>
            Status
            <select
              name="active"
              defaultValue={String(member.active)}
              disabled={!canManage || member.role === "owner"}
            >
              <option value="true">Active</option>
              <option value="false">Former</option>
            </select>
          </label>
          <span>{member.is_guest ? "Guest" : member.role}</span>
          {canManage ? <button className="secondary">Save</button> : null}
        </form>
      ))}
    </section>
  );
}

export function GroupSettingsPanel({
  group,
  update,
}: {
  group: {
    name: string;
    version: number;
    archived: boolean;
    current_user_role: string;
  };
  update: (body: object) => Promise<void>;
}) {
  const owner = group.current_user_role === "owner";
  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await update({ expected_version: group.version, name: data.get("name") });
  }
  return (
    <div className="settings-stack">
      <section>
        <p className="eyebrow">Group details</p>
        <h2>Settings</h2>
        <p className="muted">
          Only the owner can change group-wide settings. Financial history
          remains immutable.
        </p>
        <form onSubmit={rename}>
          <label>
            Group name
            <input
              name="name"
              defaultValue={group.name}
              required
              maxLength={120}
              disabled={!owner}
            />
          </label>
          {owner ? <button>Save Group Name</button> : null}
        </form>
      </section>
      <section className="danger-zone">
        <h3>{group.archived ? "Restore Group" : "Archive Group"}</h3>
        <p>
          {group.archived
            ? "Restore this group to the active directory and resume adding expenses."
            : "Hide this group from the active directory while preserving expenses, balances, settlements, members, and audit history."}
        </p>
        {owner ? (
          <button
            className={group.archived ? "secondary" : "danger"}
            onClick={() => {
              if (
                group.archived ||
                window.confirm(
                  "Archive this group? Its financial history will remain available.",
                )
              )
                void update({
                  expected_version: group.version,
                  archived: !group.archived,
                });
            }}
          >
            {group.archived ? "Restore Group" : "Archive Group"}
          </button>
        ) : null}
        <p className="muted">
          <strong>Deletion is unavailable:</strong> removing a group would erase
          shared financial records belonging to other participants. Archive it
          instead.
        </p>
      </section>
    </div>
  );
}
