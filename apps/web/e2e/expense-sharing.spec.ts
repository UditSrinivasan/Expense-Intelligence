import { expect, test } from "@playwright/test";

const groupId = "10000000-0000-4000-8000-000000000001";
const expenseId = "20000000-0000-4000-8000-000000000001";
const expense = { id: expenseId, group_id: groupId, title: "Team dinner", expense_date: "2026-10-18", currency: "INR", currency_quantum: "0.01", total: "1180.00", status: "confirmed", payers: [{ member_id: "a", display_name: "Asha", amount: "1180.00" }], participants: [{ member_id: "a", display_name: "Asha", amount: "590.00", share: "590.00", paid: "1180.00", balance: "590.00" }, { member_id: "b", display_name: "Sam", amount: "590.00", share: "590.00", paid: "0", balance: "-590.00" }], components: [{ id: "c", label: "Meal", amount: "1180.00", strategy: "equal", adjustment_type: "item", allocations: [{ member_id: "a", display_name: "Asha", amount: "590.00" }, { member_id: "b", display_name: "Sam", amount: "590.00" }] }], obligations: [{ payer_name: "Sam", payee_name: "Asha", amount: "590.00", currency: "INR" }], correction: { corrects_expense_id: null, replacement_expense_id: null }, reconciliation: { reconciled: true } };

test.beforeEach(async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.route("**/api/backend/v1/groups/**", async route => {
    const url = route.request().url();
    let body: unknown = {};
    if (url.endsWith(`/expenses/${expenseId}`)) body = expense;
    else if (url.endsWith("/members/all")) body = [];
    else if (url.endsWith("/balances") || url.endsWith("/settlements") || url.endsWith("/templates")) body = [];
    else if (url.endsWith("/debt-suggestions")) body = { suggestions: [] };
    else if (url.endsWith("/analytics")) body = { totals_by_currency: { INR: "1180.00" }, spending_by_category: {}, spending_over_time: {}, settlements_completed: 0, recent_expenses: [{ id: expenseId, description: "Team dinner", total: "1180.00", currency: "INR", expense_date: "2026-10-18" }], largest_expenses: [], currency_policy: "Original currency." };
    else body = { id: groupId, name: "Demo trip", default_currency: "INR", version: 1 };
    await route.fulfill({ json: body });
  });
});

test("opens a recent expense and copies its confirmed calculation", async ({ page }) => {
  await page.goto(`/groups/${groupId}`);
  await page.getByRole("link", { name: /Team dinner/ }).click();
  await expect(page).toHaveURL(new RegExp(`/groups/${groupId}/expenses/${expenseId}$`), { timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Team dinner" })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "Copy calculation" }).click();
  await expect(page.getByRole("status")).toContainText("Calculation copied");
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain("Sam owes Asha");
});

test("individual mode hides other members on mobile", async ({ page }) => {
  await page.goto(`/groups/${groupId}/expenses/${expenseId}`);
  await page.locator("select").first().selectOption("individual");
  await page.locator("select").nth(1).selectOption("a");
  await expect(page.getByLabel("Share preview")).toHaveValue(/Asha:/);
  await expect(page.getByLabel("Share preview")).not.toHaveValue(/Sam:/);
});
