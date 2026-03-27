const { defineConfig } = require("@playwright/test");

const chromeExecutable = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || "/usr/bin/google-chrome";

module.exports = defineConfig({
  testDir: "./tests/frontend",
  testMatch: /live-corpus\.spec\.js$/,
  timeout: 30000,
  use: {
    browserName: "chromium",
    headless: true,
    viewport: { width: 1365, height: 768 },
    launchOptions: {
      executablePath: chromeExecutable,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
  },
  webServer: {
    command: "python3 scripts/serve_frontend.py --port 4174",
    url: "http://127.0.0.1:4174/frontend/",
    reuseExistingServer: true,
    timeout: 30000,
  },
});
