const { defineConfig } = require("@playwright/test");

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
    if (require("fs").existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

const chromeExecutable = findBrowserExecutable();

module.exports = defineConfig({
  testDir: "./tests/frontend",
  testIgnore: /live-corpus\.spec\.js$/,
  timeout: 30000,
  expect: {
    timeout: 5000,
    toHaveScreenshot: {
      animations: "disabled",
      maxDiffPixelRatio: 0.02,
    },
  },
  use: {
    baseURL: "http://127.0.0.1:4173/frontend/",
    browserName: "chromium",
    headless: true,
    viewport: { width: 1440, height: 1024 },
    launchOptions: {
      executablePath: chromeExecutable,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
  },
  webServer: {
    command: "python3 scripts/serve_frontend_fixture_corpus.py --port 4173",
    url: "http://127.0.0.1:4173/frontend/",
    reuseExistingServer: true,
    timeout: 30000,
  },
});
