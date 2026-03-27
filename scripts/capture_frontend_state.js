const fs = require("fs");
const { chromium } = require("playwright");

function parseArgs(argv) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (!value.startsWith("--")) {
      continue;
    }
    parsed[value.slice(2)] = argv[index + 1];
    index += 1;
  }
  return parsed;
}

function findBrowserExecutable() {
  if (process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH) {
    return process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH;
  }
  for (const candidate of [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/brave-browser",
  ]) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.url || !args.screenshot) {
    throw new Error("expected --url and --screenshot");
  }

  const browser = await chromium.launch({
    headless: true,
    executablePath: findBrowserExecutable(),
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  try {
    const page = await browser.newPage({
      viewport: {
        width: Number.parseInt(args.width ?? "1365", 10),
        height: Number.parseInt(args.height ?? "768", 10),
      },
    });

    await page.route("https://fonts.googleapis.com/**", (route) => route.abort());
    await page.route("https://fonts.gstatic.com/**", (route) => route.abort());
    await page.goto(args.url, { waitUntil: "networkidle" });
    await page.locator("#editor-canvas").waitFor({ state: "visible" });
    await page.waitForTimeout(200);
    await page.screenshot({ path: args.screenshot, fullPage: false });

    const metrics = await page.evaluate(() => {
      const pane = document.querySelector(".editor-pane");
      const surface = document.querySelector("#editor-surface");
      const canvas = document.querySelector("#editor-canvas");
      const components = Array.from(document.querySelectorAll("[data-component-id]"));
      const visibleComponent = components
        .map((element) => ({
          id: element.getAttribute("data-component-id"),
          rect: element.getBoundingClientRect(),
        }))
        .find((entry) => entry.rect.width > 0 && entry.rect.height > 0) ?? null;
      const viewBox = canvas.viewBox.baseVal;
      return {
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight,
        },
        exampleCount: document.querySelectorAll("#example-list .example-card").length,
        wireCount: document.querySelectorAll(".editor-wire").length,
        paneRect: pane.getBoundingClientRect(),
        surfaceRect: surface.getBoundingClientRect(),
        canvasRect: canvas.getBoundingClientRect(),
        visibleComponent,
        editorEmptyStateHidden: document.querySelector("#editor-empty-state").hidden,
        viewBox: {
          x: viewBox.x,
          y: viewBox.y,
          width: viewBox.width,
          height: viewBox.height,
        },
      };
    });

    process.stdout.write(`${JSON.stringify(metrics)}\n`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error.stack || String(error));
  process.exit(1);
});
