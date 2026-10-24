import { expect, test } from "@playwright/test";

const group = {
  id: "10000000-0000-4000-8000-000000000011",
  name: "Five Friends",
  default_currency: "INR",
  version: 1,
  archived: false,
  members: ["Asha", "Ben", "Chitra", "Dev", "Ella"].map((display_name, index) => ({
    id: `20000000-0000-4000-8000-00000000001${index}`,
    display_name,
    role: index ? "member" : "owner",
    is_guest: index > 2,
  })),
};

test("guided split navigates and confirms on desktop and mobile", async ({ page }, testInfo) => {
  await page.route("**/api/backend/v1/groups", (route) => route.fulfill({ json: [group] }));
  await page.route("**/api/backend/v1/categories", (route) => route.fulfill({ json: [] }));
  await page.route(`**/api/backend/v1/groups/${group.id}/expenses/preview`, async (route) => {
    const body = route.request().postDataJSON();
    expect(body.components[0].shares).toHaveLength(5);
    expect(body.components[1]).toMatchObject({kind:"discount",discount_mode:"fixed",eligible_component_indexes:[0]});
    await route.fulfill({ json: { allocation_version: "minor-units-v1", components:[{index:0,label:"Dinner",kind:"item",amount:"110.00",basis:null},{index:1,label:"Item discount",kind:"discount",amount:"-10.00",basis:"110.00",mode:"fixed"}], allocations: group.members.flatMap((member) => [{ member_id: member.id, component_index: 0, component_label: "Dinner", input_value: null, unrounded_amount: "22.00", amount: "22.00", received_residual: false },{ member_id: member.id, component_index: 1, component_label: "Item discount", input_value: null, unrounded_amount: "-2.00", amount: "-2.00", received_residual: false }]), balances: group.members.map((member, index) => ({ member_id: member.id, paid: index ? "0.00" : "100.00", owed: "20.00", balance: index ? "-20.00" : "80.00" })) } });
  });
  await page.route(`**/api/backend/v1/groups/${group.id}/expenses`, (route) => route.fulfill({ status: 201, json: { id: "30000000-0000-4000-8000-000000000011", state: "confirmed", allocations: [], balances: [] } }));
  await page.goto(`/groups/new-expense?group=${group.id}`);
  await expect(page.getByRole("heading", { name: `Add expense · ${group.name}` })).toBeVisible();
  await page.getByLabel("Merchant or description").fill("Dinner");
  await page.getByLabel("Grand total").fill("100.00");
  await page.getByRole("button", { name: /Continue to People/ }).click();
  await page.getByRole("button", { name: "One person paid the full bill" }).click();
  await page.getByRole("button", { name: /Continue to Items/ }).click();
  await page.getByRole("textbox", { name: "Item", exact: true }).fill("Dinner");
  await page.getByLabel("Line total").fill("110.00");
  await page.getByRole("button", { name: /Continue to Taxes/ }).click();
  await page.getByRole("button", { name: "Add charge" }).click();
  await page.getByRole("group", {name:"tax"}).getByLabel("Type").selectOption("discount");
  const discount=page.getByRole("group", {name:"discount"});
  await discount.getByLabel("Label", {exact:true}).fill("Item discount");
  await discount.getByLabel("Amount", {exact:true}).fill("-10.00");
  await page.getByRole("group", {name:"Eligible items"}).getByLabel("Dinner").check();
  await page.getByRole("button", { name: /Continue to Review/ }).click();
  await expect(page.getByRole("heading", { name: "Review exact shares" })).toBeVisible();
  await expect(page.getByText("consumption ₹20.00").first()).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: `../../artifacts/ux-c/guided-split-${testInfo.project.name}.png`, fullPage: true });
  await page.getByRole("button", { name: "Confirm reconciled expense" }).click();
  await expect(page).toHaveURL(new RegExp(`/groups/${group.id}/expenses/30000000`));
});
