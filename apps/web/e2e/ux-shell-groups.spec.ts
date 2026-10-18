import { expect, test } from "@playwright/test";

const group = { id: "10000000-0000-4000-8000-000000000001", name: "Goa Trip", default_currency: "INR", version: 3, archived: false, current_user_role: "owner", last_activity_at: "2026-10-18T10:00:00Z", outstanding_by_currency: { INR: "1250.00" }, members: [{ id: "20000000-0000-4000-8000-000000000001", display_name: "Asha", role: "owner", is_guest: false }] };

test("shared navigation and group directory work on desktop", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop project only");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.route("**/api/backend/v1/groups?include_archived=true", (route) => route.fulfill({ json: [group] }));
  await page.goto("/groups");
  await expect(page.getByRole("navigation", { name: "Primary navigation" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Groups/ }).first()).toHaveAttribute("aria-current", "page");
  await expect(page.getByRole("heading", { name: "Your Groups" })).toBeVisible();
  await expect(page.getByText("₹1,250.00")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Group" })).toHaveAttribute("href", `/groups/${group.id}`);
  await page.screenshot({ path: "../../artifacts/ux-a-b/groups-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 1366, height: 768 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  // 200% zoom on a 1366 px display exposes roughly 683 CSS pixels.
  await page.setViewportSize({ width: 683, height: 768 });
  await expect(page.getByRole("heading", { name: "Your Groups" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("mobile navigation exposes every primary destination", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile project only");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/backend/v1/groups?include_archived=true", (route) => route.fulfill({ json: [] }));
  await page.goto("/groups");
  await page.locator('summary[aria-label="Open navigation"]').click();
  await expect(page.getByRole("link", { name: /Transactions/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Imports & Documents/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Settings/ })).toBeVisible();
  await page.screenshot({ path: "../../artifacts/ux-a-b/groups-mobile-menu.png", fullPage: true });
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.locator('summary[aria-label="Open navigation"]')).toBeVisible();
});
