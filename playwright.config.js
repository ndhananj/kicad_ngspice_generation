const { defineConfig } = require("@playwright/test");

const chromeExecutable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || "/usr/bin/google-chrome";

module.exports = defineConfig({
  testDir: "./tests/frontend",
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
    command: "python3 scripts/serve_frontend.py --port 4173 --fixture-root tests/fixtures/frontend_corpus",
    url: "http://127.0.0.1:4173/frontend/",
    reuseExistingServer: true,
    timeout: 30000,
  },
});
