import { expect, test, type Page } from "@playwright/test";

const profile = { display_name:"Asha",country_code:"IN",locale:"en-IN",home_currency:"INR",display_currency:"INR",time_zone:"Asia/Kolkata",onboarding_completed:true,theme:"system",accent:"ocean" };

async function mockAppearance(page: Page) {
  await page.route("**/api/backend/v1/profile", async route => {
    if (route.request().method() === "PUT") Object.assign(profile, route.request().postDataJSON());
    await route.fulfill({json:profile});
  });
}

test("theme, accent, and private feedback are accessible and persistent", async ({page}, testInfo) => {
  await mockAppearance(page);
  await page.route("**/api/backend/v1/feedback", route => route.fulfill({status:201,json:{id:"90000000-0000-4000-8000-000000000001",accepted:true}}));
  await page.goto("/settings");
  await page.getByRole("button",{name:"Dark"}).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme","dark");
  await page.getByRole("button",{name:"Emerald"}).click();
  await expect(page.locator("html")).toHaveAttribute("data-accent","emerald");
  await page.screenshot({path:`../../artifacts/g2-1/settings-dark-${testInfo.project.name}.png`,fullPage:true});
  await page.getByRole("button",{name:"Report a Bug / Suggest"}).click();
  const dialog=page.getByRole("dialog"); await expect(dialog).toBeVisible();
  await dialog.getByLabel("Feedback type").selectOption("calculation");
  await dialog.getByLabel("What happened or could improve?").fill("Synthetic selective-discount result needs review.");
  await dialog.getByRole("button",{name:"Send Private Feedback"}).click();
  await expect(dialog.getByRole("status")).toContainText("private beta report was recorded");
  await page.screenshot({path:`../../artifacts/g2-1/feedback-${testInfo.project.name}.png`,fullPage:true});
});

test("dashboard renders in light and dark themes at normal zoom", async ({page}, testInfo) => {
  test.skip(testInfo.project.name!=="desktop","desktop screenshots only"); profile.theme="light"; profile.accent="ocean"; await mockAppearance(page);
  await page.route("**/api/backend/v1/**", route => { const path=new URL(route.request().url()).pathname; if(path.endsWith("/profile")) return route.fallback(); if(path.endsWith("/experience")) return route.fulfill({json:{tour_state:"completed",tour_step:13,checklist_dismissed:true,checklist:[]}}); return route.fulfill({json:path.endsWith("/budgets")||path.endsWith("/groups")?[]:{sensitivity:"balanced",fx_policy:"Currencies remain separate.",totals:[],time_series:[],categories:[],merchants:[],history:{},insights:[],recurring:[],recent_transactions:[]}}) });
  await page.goto("/"); expect(await page.evaluate(()=>devicePixelRatio)).toBeGreaterThan(0); await expect(page.locator("html")).toHaveAttribute("data-theme","light");
  await page.screenshot({path:"../../artifacts/g2-1/dashboard-light.png",fullPage:true});
  profile.theme="dark"; profile.accent="violet"; await page.evaluate(()=>localStorage.setItem("ei-appearance-v1",JSON.stringify({theme:"dark",accent:"violet"}))); await page.reload(); await expect(page.locator("html")).toHaveAttribute("data-theme","dark"); await expect(page.locator("html")).toHaveAttribute("data-accent","violet");
  await page.screenshot({path:"../../artifacts/g2-1/dashboard-dark.png",fullPage:true});
});
