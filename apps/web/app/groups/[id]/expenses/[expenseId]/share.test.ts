import assert from "node:assert/strict";
import test from "node:test";
import { expenseText, money, type ExpenseDetail } from "./share.ts";

const detail: ExpenseDetail = { title: "Dinner", expense_date: "2026-10-18", currency: "KWD", total: "9.999", status: "confirmed", payers: [{ display_name: "A", amount: "9.999" }], participants: [{ member_id: "a", display_name: "A", amount: "4.999", share: "4.999", paid: "9.999", balance: "5.000" }, { member_id: "b", display_name: "B", amount: "5.000", share: "5.000", paid: "0", balance: "-5.000" }], components: [{ label: "Food", amount: "10.999", strategy: "exact", adjustment_type: "item", allocations: [{ display_name: "A", amount: "5.499" }, { display_name: "B", amount: "5.500" }] }, { label: "Discount", amount: "-1.000", strategy: "equal", adjustment_type: "discount", allocations: [{ display_name: "A", amount: "-0.500" }, { display_name: "B", amount: "-0.500" }] }], obligations: [{ payer_name: "B", payee_name: "A", amount: "5.000", currency: "KWD" }], reconciliation: { reconciled: true } };

test("formats currency precision and detailed backend values", () => { assert.match(money("9.999", "KWD"), /9[.,]999/); const text = expenseText(detail, "full"); assert.match(text, /Discount/); assert.match(text, /B owes A/); });
test("individual mode hides other participants and obligations", () => { const text = expenseText(detail, "individual", "a"); assert.match(text, /A:/); assert.doesNotMatch(text, /B:/); assert.doesNotMatch(text, /owes/); });
