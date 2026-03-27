const { test, expect } = require("@playwright/test");

async function stabilizeFonts(page) {
  await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
  await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
}

async function openWorkbench(page) {
  await stabilizeFonts(page);
  await page.goto("./?test=1");
  await expect(page.locator("#hero-title")).toHaveText("RC Low-pass");
  await expect(page.getByRole("tab", { name: "Editor" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-component-id="R1"]')).toBeVisible();
}

const smokeExamples = [
  {
    id: "rc_lowpass",
    name: "RC Low-pass",
    availableTabs: ["Editor", "circuitikz.tex", "report.tex", "ngspice.cir"],
    availableLinks: ["editor.scene.json", "preview.svg", "circuitikz.tex", "report.tex", "ngspice.cir", "schematic.kicad_sch"],
    unavailableLinks: ["report.pdf"],
  },
  {
    id: "rc_highpass",
    name: "RC High-pass",
    availableTabs: ["Editor", "circuitikz.tex", "ngspice.cir"],
    availableLinks: ["editor.scene.json", "circuitikz.tex", "ngspice.cir", "schematic.kicad_sch"],
    unavailableLinks: ["preview.svg", "report.tex", "report.pdf"],
  },
  {
    id: "diode_clipper",
    name: "Diode Clipper",
    availableTabs: ["Editor", "circuitikz.tex", "report.tex", "ngspice.cir"],
    availableLinks: ["editor.scene.json", "circuitikz.tex", "report.tex", "ngspice.cir", "schematic.kicad_sch"],
    unavailableLinks: ["preview.svg", "report.pdf"],
  },
];

async function expectArtifactAvailability(page, labels, available) {
  for (const label of labels) {
    const target = page.locator("#artifact-list").getByText(label, { exact: true }).locator("..");
    if (available) {
      await expect(target).not.toHaveClass(/unavailable/);
      continue;
    }
    await expect(target).toHaveClass(/unavailable/);
  }
}

async function selectExample(page, example) {
  await page.locator('[data-example-id="' + example.id + '"]').click();
  await expect(page.locator("#hero-title")).toHaveText(example.name);
}

test("supports selecting, dragging, and nudging components in the editor", async ({ page }) => {
  await openWorkbench(page);

  const resistor = page.locator('[data-component-id="R1"]');
  await resistor.click();
  await expect(resistor).toHaveClass(/active/);

  const before = await resistor.boundingBox();
  await page.mouse.move(before.x + before.width / 2, before.y + before.height / 2);
  await page.mouse.down();
  await page.mouse.move(before.x + before.width / 2 + 56, before.y + before.height / 2 + 28);
  await page.mouse.up();

  const afterDrag = await resistor.boundingBox();
  expect(afterDrag.x).toBeGreaterThan(before.x + 10);

  await page.locator("#editor-canvas").focus();
  await page.keyboard.press("ArrowRight");
  const afterNudge = await resistor.boundingBox();
  expect(afterNudge.x).toBeGreaterThan(afterDrag.x);

  await page.keyboard.press("Delete");
  await expect(resistor).not.toHaveClass(/active/);
});

test("preserves the active tab and updates the preview when switching examples", async ({ page }) => {
  await openWorkbench(page);

  await expect(page.locator("#example-list .example-card")).toHaveCount(3);

  await page.getByRole("tab", { name: "report.tex" }).click();
  await expect(page.locator("#preview-caption")).toContainText("report preview");
  await expect(page.locator("#document-state")).toBeVisible();
  await expect(page.locator("#document-state-copy")).toContainText("rendered report PDF is missing");
  await expect(page.locator("#preview-frame")).toBeHidden();

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

test("shows the declared artifact surface for each smoke example", async ({ page }) => {
  await openWorkbench(page);

  for (const example of smokeExamples) {
    await selectExample(page, example);
    await expectArtifactAvailability(page, example.availableLinks, true);
    await expectArtifactAvailability(page, example.unavailableLinks, false);
    for (const tab of example.availableTabs) {
      await expect(page.getByRole("tab", { name: tab })).not.toHaveClass(/unavailable/);
    }
    for (const tab of ["Editor", "circuitikz.tex", "report.tex", "ngspice.cir"]) {
      if (!example.availableTabs.includes(tab)) {
        await expect(page.getByRole("tab", { name: tab })).toHaveClass(/unavailable/);
      }
    }
  }
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
