import { expect, test, type Page } from "@playwright/test";

const transaction = { id: "10000000-0000-4000-8000-000000000001", description: "Corner Shop", category: "Groceries", category_id: null, classification_source: "unclassified", original_amount: "1250.00", original_currency: "INR", effective_date: "2026-10-20", posting_date: null, direction: "expense", transaction_type: "purchase", needs_review: true, account_id: "20000000-0000-4000-8000-000000000001", import_batch_id: "30000000-0000-4000-8000-000000000001", source_reference: "SYNTH-1" };
const categories = [{ id: "40000000-0000-4000-8000-000000000001", name: "Food", parent_id: null }, { id: "40000000-0000-4000-8000-000000000002", name: "Groceries", parent_id: "40000000-0000-4000-8000-000000000001" }];
const accounts = [{ id: transaction.account_id, name: "Daily Account", currency: "INR" }];

async function mockFinance(page: Page) {
  await page.route("**/api/backend/v1/**", async (route) => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method();
    if (method === "POST" && path.endsWith("/transactions")) return route.fulfill({ status: 201, json: transaction });
    if (path.endsWith("/analytics/overview")) return route.fulfill({ json: { sensitivity: "balanced", fx_policy: "Currencies are never combined.", totals: [{ currency: "INR", spend: "950.00", income: "3000.00", cash_outflow: "1250.00", cash_income: "3000.00", cash_net: "1750.00", shared_consumption: "200.00" }], time_series: [{ currency: "INR", period: "2026-10", spend: "950.00" }], categories: [{ currency: "INR", name: "Groceries", spend: "750.00" }], merchants: [{ currency: "INR", name: "Corner Shop", spend: "750.00" }], history: { unusual_amount: true }, insights: [{ id: "insight-1", currency: "INR", title: "Possible duplicate", explanation: "Same merchant and amount appeared twice.", severity: "warning", evidence: { transaction_ids: [transaction.id], method: "exact evidence" } }], recurring: [], recent_transactions: [{ id: transaction.id, date: transaction.effective_date, description: transaction.description, amount: transaction.original_amount, currency: "INR", direction: "expense", type: "purchase", imported: true }] } });
    if (path.endsWith("/budgets")) return route.fulfill({ json: [{ budget: { id: "budget-1", name: "Monthly Food", currency: "INR" }, remaining: "2500.00", utilization_percent: "50", warning_state: "on_track" }] });
    if (path.endsWith("/groups")) return route.fulfill({ json: [{ id: "group-1", name: "Flat", outstanding_by_currency: { INR: "-500.00" } }] });
    if (path.endsWith("/transactions")) return route.fulfill({ json: [transaction] });
    if (path.endsWith("/categories")) return route.fulfill({ json: categories });
    if (path.endsWith("/classification-rules")) return route.fulfill({ json: [] });
    if (path.endsWith("/accounts")) return route.fulfill({ json: accounts });
    if (path.endsWith("/imports")) return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
}

test("dashboard separates cash flow and consumption with traceable records", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop project only"); await mockFinance(page); await page.goto("/");
  await expect(page.getByRole("heading", { name: "Know where your money went." })).toBeVisible();
  await expect(page.getByText("Personal consumption", { exact: true })).toBeVisible(); await expect(page.getByText("Net cash flow", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /Corner Shop/ }).last()).toHaveAttribute("href", `/transactions?ids=${transaction.id}`);
  await expect(page.getByRole("heading", { name: "Budget Progress" })).toBeVisible(); await expect(page.getByRole("heading", { name: "Group Balances" })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ux-e/dashboard-desktop.png", fullPage: true });
});

test("transactions expose filters, manual entry, and import provenance", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop project only"); await mockFinance(page); await page.goto("/transactions?add=true");
  await expect(page.getByRole("heading", { name: "Add a Transaction" })).toBeVisible();
  await page.getByLabel("Description").fill("Synthetic income"); await page.getByLabel("Amount").fill("100.25"); await page.getByLabel("Direction").selectOption("income"); await page.locator('.manual-transaction select[name="type"]').selectOption("income"); await page.locator(".manual-transaction").getByRole("button", { name: "Add Transaction" }).click();
  await expect(page.getByRole("status")).toContainText("Transaction added"); await page.getByText("Details & provenance").click();
  await expect(page.getByText("Imported statement")).toBeVisible(); await expect(page.getByText("SYNTH-1")).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ux-e/transactions-desktop.png", fullPage: true });
});

test("mobile import entry offers every ingestion path without overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile project only"); await mockFinance(page); await page.goto("/imports");
  await expect(page.getByRole("navigation", { name: "Add financial records" })).toBeVisible(); await expect(page.getByRole("link", { name: "Scan Receipt or PDF" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: "../../artifacts/ux-e/imports-mobile.png", fullPage: true });
});
