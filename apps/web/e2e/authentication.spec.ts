import { expect, test } from "@playwright/test";

test("shows a clear unconfigured Google sign-in state", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: /Your finances/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
  await expect(page.getByText(/not configured/)).toBeVisible();
});

test("allows unauthenticated requests to reach the OAuth initiation route", async ({ page }) => {
  await page.goto("/auth/login");
  await expect(page).toHaveURL(/\/login\?error=configuration$/);
});

test("completes explicit India or UK onboarding without a browser identity header", async ({ page }) => {
  let saved: Record<string, unknown> | undefined;
  await page.route("**/api/backend/v1/profile", async route => {
    expect(route.request().headers()["x-dev-user-id"]).toBeUndefined();
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { display_name:"", country_code:"IN", locale:"en-IN", home_currency:"INR", display_currency:"INR", time_zone:"Asia/Kolkata", onboarding_completed:false } });
    } else {
      saved = route.request().postDataJSON();
      await route.fulfill({ json: { ...saved, onboarding_completed:true } });
    }
  });
  await page.route("**/api/backend/v1/analytics/**", route => route.fulfill({ json: { sensitivity:"balanced",fx_policy:"",totals:[],time_series:[],categories:[],history:{},insights:[],recurring:[] } }));
  await page.goto("/onboarding");
  await expect(page.getByRole("button", { name: "Finish setup" })).toBeEnabled();
  await page.getByLabel("Display name").fill("Priya");
  await page.getByLabel("Country").selectOption("GB");
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect.poll(() => saved?.country_code).toBe("GB");
  expect(saved?.home_currency).toBe("GBP");
  expect(saved?.time_zone).toBe("Europe/London");
});
