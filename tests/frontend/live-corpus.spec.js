const { test, expect } = require("@playwright/test");

async function stabilizeFonts(page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
  await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
}

test("keeps the initial editor content inside the visible pane on the real corpus", async ({ page }) => {
  await stabilizeFonts(page);
  await page.goto("http://127.0.0.1:4174/frontend/?test=1", { waitUntil: "networkidle" });

  await expect(page.locator("#example-list .example-card")).toHaveCount(8);
  await expect.poll(async () => page.locator(".editor-wire").count()).toBeGreaterThan(0);

  const viewport = page.viewportSize();
  const paneBox = await page.locator(".editor-pane").boundingBox();
  const componentBox = await page.locator('[data-component-id="R1"]').boundingBox();
  expect(paneBox.height).toBeLessThan(viewport.height * 0.82);
  expect(componentBox.y).toBeLessThan(paneBox.y + paneBox.height * 0.6);
});
