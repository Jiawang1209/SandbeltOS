import { test, expect } from "@playwright/test";

test.describe("Dashboard ChatWidget", () => {
  test("widget button opens the panel", async ({ page }) => {
    await page.goto("/dashboard");
    const btn = page.getByRole("button", { name: /打开.*问答/ });
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page.getByText("SandbeltOS Copilot")).toBeVisible();
  });

  test("widget ask injects region and gets sources", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /打开.*问答/ }).click();
    await page.getByRole("button", { name: "现在风险怎么样？" }).click();
    // Source pills eventually appear
    await expect(page.getByText(/\[1\]/).first()).toBeVisible({
      timeout: 15_000,
    });
  });

  test("widget full-screen link navigates to /chat", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /打开.*问答/ }).click();
    await page.getByRole("link", { name: /全屏/ }).click();
    await expect(page).toHaveURL(/\/chat$/);
  });

  test("widget close hides the panel", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("button", { name: /打开.*问答/ }).click();
    await page.getByRole("button", { name: "关闭" }).click();
    await expect(
      page.getByRole("button", { name: /打开.*问答/ }),
    ).toBeVisible();
  });
});
