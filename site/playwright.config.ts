import { defineConfig } from "@playwright/test";

// Needs the site built with LOCAL_API=1 (npm run build with that variable) so /api is forwarded to the local Python server.
export default defineConfig({
  testDir: "./tests",
  timeout: 120000,
  use: { baseURL: "http://127.0.0.1:3100" },
  webServer: [
    { command: "npm run api", url: "http://127.0.0.1:8765/api/calc?q=%7B%7D", reuseExistingServer: true, timeout: 120000 },
    { command: "npx next start -p 3100", url: "http://127.0.0.1:3100", reuseExistingServer: true, timeout: 120000, env: { LOCAL_API: "1" } },
  ],
});
