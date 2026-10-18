export type Allocation = { display_name: string; amount: string };
export type ExpenseDetail = { title: string; expense_date: string; currency: string; total: string; status: string; payers: Allocation[]; participants: (Allocation & { share: string; paid: string; balance: string; member_id: string })[]; components: { label: string; amount: string; strategy: string; adjustment_type: string; allocations: Allocation[] }[]; obligations: { payer_name: string; payee_name: string; amount: string; currency: string }[]; group_outstanding?: { member_id: string; display_name: string; balance: string }[]; settlement_history?: { payer_member_id: string; payer_name: string; payee_member_id: string; payee_name: string; amount: string; status: string; kind: string; date: string }[]; correction?: { corrects_expense_id: string | null; replacement_expense_id: string | null }; reconciliation: { reconciled: boolean } };
export type Privacy = "full" | "summary" | "individual";

export function money(amount: string, currency: string) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(amount));
}

export function expenseText(expense: ExpenseDetail, privacy: Privacy, participant?: string) {
  const m = (amount: string) => money(amount, expense.currency);
  const visible = privacy === "individual" ? expense.participants.filter((row) => row.member_id === participant) : expense.participants;
  const lines = [`${expense.title} — ${new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${expense.expense_date}T00:00:00Z`))}`, `Total: ${m(expense.total)}`, "", "Shares:", ...visible.map((row) => `${row.display_name}: ${m(row.share)}`)];
  if (privacy !== "individual") lines.push("", "Who owes whom:", ...(expense.obligations.length ? expense.obligations.map((row) => `${row.payer_name} owes ${row.payee_name} ${m(row.amount)}`) : ["Everyone is settled for this expense."]));
  if (privacy === "full") lines.push("", "Detailed breakdown:", ...expense.components.flatMap((item) => [`${item.label}: ${m(item.amount)} (${item.strategy.replaceAll("_", " ")}; ${item.adjustment_type.replaceAll("_", " ")})`, ...item.allocations.map((row) => `  ${row.display_name}: ${m(row.amount)}`)]), "", `Paid by: ${expense.payers.map((row) => `${row.display_name} ${m(row.amount)}`).join(", ")}`);
  const settlements = privacy === "individual" ? expense.settlement_history?.filter((row) => row.payer_member_id === participant || row.payee_member_id === participant) : expense.settlement_history;
  if (privacy !== "summary" && settlements?.length) lines.push("", "Recorded settlements:", ...settlements.map((row) => `${row.date}: ${row.payer_name} paid ${row.payee_name} ${m(row.amount)} (${row.kind}, ${row.status})`));
  if (privacy !== "summary" && expense.group_outstanding?.length) {
    const outstanding = privacy === "individual" ? expense.group_outstanding.filter((row) => row.member_id === participant) : expense.group_outstanding;
    if (outstanding.length) lines.push("", "Current group position:", ...outstanding.map((row) => `${row.display_name}: ${m(row.balance)}`));
  }
  return lines.join("\n");
}
