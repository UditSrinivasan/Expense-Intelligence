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

test("detects and reconciles first-class USD and EUR documents", () => {
  const usd = extractReceipt(
    "DEMO CAFE\n18/10/2026\nLunch $12.50\nTax $1.00\nTOTAL $13.50",
  );
  const eur = extractStatement(
    "Statement EUR\n18/10/2026 MARKET EUR 20.00",
  );
  assert.equal(usd.currency, "USD");
  assert.equal(usd.total, "13.50");
  assert.deepEqual(usd.issues, []);
  assert.equal(eur[0].currency, "EUR");
  assert.equal(eur[0].amount, "20.00");
});

test("reports receipt mismatch instead of inventing reconciliation", () => {
  const receipt = extractReceipt("SHOP\n18/10/2026\nItem £9.99\nTOTAL £10.00");
  assert.match(receipt.issues.join(" "), /reconcile/);
});

test("aggregates restaurant taxes and platform fees without inventing items", () => {
  const receipt = extractReceipt("SYNTHETIC SWIGGY ORDER\n24/10/2026\nPaneer meal INR 300.00\nGST INR 15.00\nRestaurant tax INR 9.00\nDelivery fee INR 20.00\nPackaging fee INR 10.00\nPlatform discount INR 30.00\nTOTAL INR 324.00");
  assert.equal(receipt.tax, "24.00");
  assert.equal(receipt.delivery_fee, "20.00");
  assert.equal(receipt.packaging_fee, "10.00");
  assert.equal(receipt.discount, "-30.00");
  assert.deepEqual(receipt.issues, []);
});

test("keeps included tax at zero and requires review for illegible conflicts", () => {
  const receipt = extractReceipt("SYNTHETIC GROCERY\n24/10/2026\nMilk INR 42.00\nGST included INR 7.56\nIllegible item INR 1?.00\nTOTAL INR 50.00");
  assert.equal(receipt.tax, "0.00");
  assert.match(receipt.issues.join(" "), /reconcile/);
  assert.ok(receipt.confidence <= 0.7);
});
