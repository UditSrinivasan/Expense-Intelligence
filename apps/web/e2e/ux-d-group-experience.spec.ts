import { expect, test } from "@playwright/test";

const groupId = "10000000-0000-4000-8000-000000000001";
const ownerId = "20000000-0000-4000-8000-000000000001";
const guestId = "20000000-0000-4000-8000-000000000002";
const group = { id: groupId, name: "Goa Trip", default_currency: "INR", version: 3, archived: false, current_user_role: "owner" };
const members = [{ id: ownerId, display_name: "Asha", role: "owner", active: true, is_guest: false }, { id: guestId, display_name: "Ben", role: "member", active: true, is_guest: true }];
const suggestion = { payer_member_id: guestId, payer_name: "Ben", payee_member_id: ownerId, payee_name: "Asha", amount: "500.00", currency: "INR", explanation: "Suggestion only" };
const analytics = { totals_by_currency: { INR: "1000.00" }, spending_by_category: { Food: { INR: "1000.00" } }, spending_over_time: { "2026-10-18": { INR: "1000.00" } }, settlements_completed: 0, recent_expenses: [{ id: "30000000-0000-4000-8000-000000000001", description: "Dinner", total: "1000.00", currency: "INR", expense_date: "2026-10-18" }], largest_expenses: [], currency_policy: "Original currencies remain separate." };

async function mockWorkspace(page: import("@playwright/test").Page) {
  await page.route(`**/api/backend/v1/groups/${groupId}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== "GET") return route.fulfill({ json: { id: "saved" } });
    if (path.endsWith("/members/all")) return route.fulfill({ json: members });
    if (path.endsWith("/balances")) return route.fulfill({ json: [] });
    if (path.endsWith("/debt-suggestions")) return route.fulfill({ json: { suggestions: [suggestion] } });
    if (path.endsWith("/settlements")) return route.fulfill({ json: [] });
    if (path.endsWith("/templates")) return route.fulfill({ json: [{ id: "40000000-0000-4000-8000-000000000001", name: "Rent", description: "Monthly rent", currency: "INR", version: 2, active: true, components: [{ label: "Rent", amount: "20000.00", strategy: "weighted", shares: [] }] }] });
    if (path.endsWith("/analytics")) return route.fulfill({ json: analytics });
    if (path.endsWith("/activity")) return route.fulfill({ json: { expenses: [{ id: analytics.recent_expenses[0].id, description: "Dinner", amount: "1000.00", currency: "INR", date: "2026-10-18", status: "confirmed", corrects_expense_id: null }], settlements: [] } });
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });
  await page.route(`**/api/backend/v1/groups/${groupId}`, (route) => route.fulfill({ json: group }));
}

test("settlement preview, templates, and searchable history are usable", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop project only");
  await mockWorkspace(page);
  await page.goto(`/groups/${groupId}?tab=settle`);
  await page.getByRole("button", { name: "Balances & Settle" }).click();
  await page.getByRole("button", { name: "Review Settlement" }).click();
  await expect(page.getByRole("dialog", { name: "Confirm recorded settlement" })).toContainText("does not move money");
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.getByRole("button", { name: "Templates" }).click();
  await expect(page.getByText("Monthly rent · v2")).toBeVisible();
  await page.getByRole("button", { name: "History" }).click();
  await expect(page.getByRole("heading", { name: "Group History" })).toBeVisible();
  await page.getByRole("searchbox", { name: "Search history" }).fill("Dinner");
  await expect(page.getByRole("link", { name: /Dinner/ })).toBeVisible();
});

test("group settlement experience has no mobile horizontal overflow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile project only");
  await mockWorkspace(page);
  await page.goto(`/groups/${groupId}?tab=settle`);
  await page.getByRole("button", { name: "Balances & Settle" }).click();
  await expect(page.getByRole("button", { name: "Review Settlement" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});
