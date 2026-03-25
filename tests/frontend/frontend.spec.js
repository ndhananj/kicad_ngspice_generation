const { test, expect } = require("@playwright/test");

async function stabilizeFonts(page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
  await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
}

async function openWorkbench(page) {
  await stabilizeFonts(page);
  await page.goto("./?test=1");
  await expect(page.locator("#hero-title")).toHaveText("RC Low-pass");
  await expect(page.locator("#source-code")).toContainText("\\draw");
}

test("preserves the active tab and updates the preview when switching examples", async ({ page }) => {
  await openWorkbench(page);

  await expect(page.locator("#example-list .example-card")).toHaveCount(3);

  await page.getByRole("tab", { name: "report.tex" }).click();
  await expect(page.locator("#preview-frame")).toBeVisible();
  await expect(page.locator("#preview-open-link")).toHaveAttribute("href", /rc_lowpass\.pdf$/);
  await expect(page.locator("#preview-caption")).toContainText("report preview");

  await page.locator('[data-example-id="rc_highpass"]').click();
  await expect(page.getByRole("tab", { name: "report.tex" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#active-file-label")).toHaveText("report.tex");
  await expect(page.locator("#source-status")).toContainText("Unable to load report.tex.");
  await expect(page.locator("#document-state")).toBeVisible();
  await expect(page.locator("#document-state-title")).toHaveText("Report preview unavailable");
  await expect(page.locator("#document-state-copy")).toContainText("does not include report.pdf");
  await expect(page.locator("#preview-frame")).toBeHidden();
});

test("shows owned fallback states for missing visual previews", async ({ page }) => {
  await openWorkbench(page);

  await page.locator('[data-example-id="diode_clipper"]').click();
  await expect(page.locator("#preview-state")).toBeVisible();
  await expect(page.locator("#preview-state-title")).toHaveText("Preview unavailable");
  await expect(page.locator("#preview-state-copy")).toContainText("No SVG preview is available");
  await expect(page.locator("#preview-open-link")).toHaveAttribute("aria-disabled", "true");
});

test("clears stale preview fallback when switching to an example with a real preview", async ({ page }) => {
  await openWorkbench(page);

  await page.locator('[data-example-id="diode_clipper"]').click();
  await expect(page.locator("#preview-state")).toBeVisible();

  await page.locator('[data-example-id="rc_lowpass"]').click();
  await expect(page.locator("#preview-state")).toBeHidden();
  await expect(page.locator("#preview-image")).toBeVisible();
  await expect(page.locator("#preview-image")).toHaveAttribute("src", /rc_lowpass\.svg$/);
});

test("matches the desktop workbench visual baseline", async ({ page }) => {
  await openWorkbench(page);
  await expect(page).toHaveScreenshot("workbench-desktop.png");
});

test("matches the report preview visual baseline on mobile", async ({ page }) => {
  await stabilizeFonts(page);
  await page.setViewportSize({ width: 430, height: 932 });
  await page.goto("./?test=1");
  await page.getByRole("tab", { name: "report.tex" }).click();
  await expect(page).toHaveScreenshot("report-preview-mobile.png");
});
