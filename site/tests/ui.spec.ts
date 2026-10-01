import { expect, test } from "@playwright/test";

test("every number on the calculator has an ⓘ, the ⓘ opens its working, and a new amount recalculates", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Up to date")).toBeVisible({ timeout: 90000 });
  const figures = page.locator("[data-money]");
  const count = await figures.count();
  expect(count).toBeGreaterThan(40);
  for (let i = 0; i < count; i++) {
    await expect(figures.nth(i).locator("button.info")).toHaveCount(1);
  }
  await figures.first().locator("button.info").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.locator(".trace, .explain")).toBeVisible();
  await dialog.getByRole("button", { name: "Close" }).click();
  const head = page.locator("article[data-option^='PRODUCT_'] .money.big");
  const before = await head.getAttribute("data-money");
  await page.locator("input[name=amount]").fill("500000");
  await expect(page.getByText("Working it out")).toBeVisible();
  await expect(page.getByText("Up to date")).toBeVisible({ timeout: 90000 });
  await expect(head).not.toHaveAttribute("data-money", before!);
});

test("a start before the model's first year is a message, not a number", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Up to date")).toBeVisible({ timeout: 90000 });
  await page.locator("input[name=start]").fill("2011-04-01");
  await expect(page.locator(".messages")).toContainText("2013-04-01", { timeout: 90000 });
});

test("the Fyers page shows a past day's orders as Fyers API payloads, marked preview only", async ({ page }) => {
  await page.goto("/fyers");
  await expect(page.getByText("PREVIEW ONLY")).toBeVisible();
  await expect(page.locator(".order pre").first()).toContainText('"productType": "CNC"', { timeout: 90000 });
});
