import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

type Experience = { tour_state: "never_started" | "in_progress" | "completed" | "skipped"; tour_step: number; checklist_dismissed: boolean; checklist: { key: string; label: string; href: string; completed: boolean }[] };
const checklist = [
  ["profile", "Complete your profile", "/settings", true], ["transaction", "Add your first transaction", "/transactions?add=true", false], ["import", "Import a statement or scan a receipt", "/imports", false], ["budget", "Create a budget", "/budgets", false], ["group", "Create or join a group", "/groups", false], ["split", "Try an expense split", "/groups/tutorial", false], ["dashboard", "Review your dashboard", "/", false],
].map(([key, label, href, completed]) => ({ key: String(key), label: String(label), href: String(href), completed: Boolean(completed) }));
const tutorial = { label: "Tutorial example", currency: "INR", subtotal: 4200, total: 4798, reconciled: true, participants: [{ name:"Asha",paid:3000,consumed:1900,balance:1100 },{ name:"Ben",paid:0,consumed:1700,balance:-1700 },{ name:"Chitra",paid:0,consumed:500,balance:-500 },{ name:"Dev",paid:1798,consumed:398,balance:1400 },{ name:"Ella",paid:0,consumed:300,balance:-300 }], components: [{ label:"Wine",amount:1500,rule:"Non-drinkers are excluded",allocations:[{name:"Asha",amount:750},{name:"Ben",amount:750}]},{ label:"Tax",amount:378,rule:"Allocated in proportion to item consumption",allocations:[{name:"Asha",amount:189},{name:"Ben",amount:189}]}], settlements: [{ payer_name:"Ben",payee_name:"Dev",amount:1400,currency:"INR",explanation:"Suggestion only"},{payer_name:"Ben",payee_name:"Asha",amount:300,currency:"INR",explanation:"Suggestion only"},{payer_name:"Chitra",payee_name:"Asha",amount:500,currency:"INR",explanation:"Suggestion only"},{payer_name:"Ella",payee_name:"Asha",amount:300,currency:"INR",explanation:"Suggestion only"}] };

async function mockApp(page: Page, initial: Partial<Experience> = {}) {
  let state: Experience = { tour_state: "never_started", tour_step: 0, checklist_dismissed: false, checklist, ...initial };
  await page.route("**/api/backend/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/experience")) {
      if (route.request().method() === "PUT") { const update = route.request().postDataJSON(); state = { ...state, ...update }; if (update.dashboard_reviewed) state.checklist = state.checklist.map(item => item.key === "dashboard" ? { ...item, completed:true } : item); }
      return route.fulfill({ json: state });
    }
    if (path.endsWith("/tutorials/five-friends-split")) return route.fulfill({ json: tutorial });
    if (path.endsWith("/profile")) return route.fulfill({ json: { display_name:"Priya",country_code:"IN",locale:"en-IN",home_currency:"INR",display_currency:"INR",time_zone:"Asia/Kolkata",onboarding_completed:true } });
    if (path.endsWith("/analytics/overview")) return route.fulfill({ json: { sensitivity:"balanced",fx_policy:"Currencies remain separate.",totals:[],time_series:[],categories:[],merchants:[],history:{unusual_amount:false},insights:[],recurring:[],recent_transactions:[] } });
    if (path.endsWith("/flags") || path.endsWith("/chat/threads") || path.endsWith("/transactions") || path.endsWith("/budgets") || path.endsWith("/groups") || path.endsWith("/accounts") || path.endsWith("/imports") || path.endsWith("/categories") || path.endsWith("/classification-rules")) return route.fulfill({ json: [] });
    if (path.endsWith("/feedback")) return route.fulfill({ status:201, json:{ id:"90000000-0000-4000-8000-000000000001",accepted:true } });
    return route.fulfill({ json: {} });
  });
  return () => state;
}

test("first-time tour starts, crosses routes, skips a section, and persists", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop journey only"); const state = await mockApp(page); await page.goto("/");
  await expect(page.getByRole("heading", { name:"Welcome to Expense Intelligence" })).toBeVisible(); await page.getByRole("button", { name:"Start tour" }).click();
  await expect(page.getByText("Step 1 of 13", { exact:true }).first()).toBeVisible(); await page.getByRole("button", { name:"Next", exact:true }).click(); await expect(page).toHaveURL(/transactions\?add=true/);
  await page.getByRole("button", { name:"Skip section" }).click(); await expect(page.getByText("Import statements")).toBeVisible();
  await page.reload(); await expect(page.getByText("Import statements")).toBeVisible(); expect(state().tour_state).toBe("in_progress"); expect(state().tour_step).toBe(2);
});

test("tour can be skipped and replayed from settings", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop journey only"); const state = await mockApp(page); await page.goto("/"); await page.getByRole("button", { name:"Skip tour" }).click(); expect(state().tour_state).toBe("skipped");
  await page.goto("/settings"); await page.getByRole("button", { name:"Replay product tour" }).click(); await expect(page.getByText("Step 1 of 13", { exact:true }).first()).toBeVisible();
});

test("completion persists without changing another account's onboarding state", async ({ page, context }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "desktop journey only");
  const first = await mockApp(page, { tour_state:"in_progress", tour_step:12 }); await page.goto("/settings"); await page.getByRole("button", { name:"Finish" }).click(); expect(first().tour_state).toBe("completed"); await page.reload(); await expect(page.getByRole("heading", { name:"Privacy by default" })).toBeVisible(); await expect(page.getByRole("heading", { name:"Privacy and preferences" })).toBeHidden();
  const otherPage = await context.newPage(); const second = await mockApp(otherPage); await otherPage.goto("/"); await expect(otherPage.getByRole("heading", { name:"Welcome to Expense Intelligence" })).toBeVisible(); expect(second().tour_state).toBe("never_started"); await otherPage.close();
});

test("checklist uses action state and tutorial reconciles on mobile", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile", "mobile journey only"); await mockApp(page, { tour_state:"skipped" }); await page.goto("/");
  await expect(page.getByRole("heading", { name:"Your checklist" })).toBeVisible(); await page.getByRole("button", { name:"Mark reviewed" }).click(); await expect(page.getByText("Review your dashboard").locator("..")).toHaveClass(/complete/);
  await page.goto("/groups/tutorial"); await expect(page.getByRole("heading", { name:"Five friends. One exact bill." })).toBeVisible(); await expect(page.getByText("Exact", { exact:true })).toBeVisible(); await expect(page.getByText("Non-drinkers are excluded")).toBeHidden(); await page.getByText("Wine", { exact:true }).click(); await expect(page.getByText("Non-drinkers are excluded")).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true); await page.screenshot({ path:"../../artifacts/ux-f/tutorial-mobile.png", fullPage:true });
});

test("assistant labels isolation and key pages have no serious axe violations", async ({ page }, testInfo) => {
  await mockApp(page, { tour_state:"completed", checklist_dismissed:true }); await page.goto("/assistant"); await expect(page.getByText("Synthetic · disconnected")).toBeVisible(); await expect(page.getByText(/No private records/)).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze(); expect(results.violations.filter(item => ["critical", "serious"].includes(item.impact ?? ""))).toEqual([]);
  if (testInfo.project.name === "desktop") await page.screenshot({ path:"../../artifacts/ux-f/assistant-desktop.png", fullPage:true });
});
