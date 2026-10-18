import assert from "node:assert/strict";
import test from "node:test";
import { addMoney, extractReceipt, extractStatement } from "./document.ts";

test("extracts and reconciles a synthetic UK receipt", () => {
  const receipt = extractReceipt(
    "GREEN MARKET\n18/10/2026\nGroceries £25.00\nWine £12.00\nHousehold £8.00\nTOTAL £45.00",
  );
  assert.equal(receipt.currency, "GBP");
  assert.equal(receipt.total, "45.00");
  assert.equal(addMoney(receipt.items.map((item) => item.line_total)), "45.00");
  assert.deepEqual(receipt.issues, []);
});

test("extracts India GST evidence and exact discount reconciliation", () => {
  const receipt = extractReceipt(
    "NANDINI STORE\n18/10/2026\nFood ₹100.00\nDiscount ₹10.00\nGST ₹18.00\nTOTAL ₹108.00",
  );
  assert.equal(receipt.currency, "INR");
  assert.equal(receipt.discount, "-10.00");
  assert.equal(receipt.tax, "18.00");
  assert.equal(
    addMoney([
      ...receipt.items.map((item) => item.line_total),
      receipt.discount,
      receipt.tax,
    ]),
    "108.00",
  );
});

test("extracts conservative statement rows", () => {
  const rows = extractStatement(
    "Statement INR\n18/10/2026 UPI SHOP 125.50\n19/10/2026 SALARY CREDIT 50000.00",
  );
  assert.equal(rows.length, 2);
  assert.equal(rows[0].direction, "expense");
  assert.equal(rows[1].direction, "income");
  assert.equal(rows[0].amount, "125.50");
});

test("reports receipt mismatch instead of inventing reconciliation", () => {
  const receipt = extractReceipt("SHOP\n18/10/2026\nItem £9.99\nTOTAL £10.00");
  assert.match(receipt.issues.join(" "), /reconcile/);
});
