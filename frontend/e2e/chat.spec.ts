import { test, expect } from "@playwright/test";

test.describe("/chat", () => {
  test("shows empty state with example questions", async ({ page }) => {
    await page.goto("/chat");
    // EmptyState heading (distinct from the banner h1 with the same text).
    await expect(
      page.getByRole("main").getByRole("heading", {
        name: "SandbeltOS 智慧问答",
      }),
    ).toBeVisible();
    await expect(page.getByText("风险评估")).toBeVisible();
    await expect(page.getByText("物种选择")).toBeVisible();
  });

  test("clicking an example streams a response", async ({ page }) => {
    await page.goto("/chat");
    await page.getByRole("button", { name: /RWEQ 公式/ }).click();

    await expect(page.getByText("你", { exact: false })).toBeVisible();

    await expect(page.locator("#source-1")).toBeVisible({ timeout: 15_000 });

    await expect(page.locator(".prose").first()).not.toHaveText("...", {
      timeout: 20_000,
    });
  });

  test("new conversation resets", async ({ page }) => {
    await page.goto("/chat");
    // Use RWEQ question — retrieval reliably returns sources for it.
    await page.getByRole("button", { name: /RWEQ 公式/ }).click();
    await expect(page.locator("#source-1")).toBeVisible({ timeout: 15_000 });
    // The "新对话" button is disabled while streaming — wait for it to re-enable
    // (which happens when the `done` SSE event clears the streaming flag).
    const resetBtn = page.getByRole("button", { name: "新对话" });
    await expect(resetBtn).toBeEnabled({ timeout: 60_000 });
    await resetBtn.click();
    await expect(page.getByText("风险评估")).toBeVisible();
  });
});
