import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  // In production Firebase Hosting rewrites /api/** to the Cloud Run service.
  server: { port: 5173, proxy: { "/api": "http://localhost:8080" } },
  test: { environment: "jsdom", setupFiles: "./src/test-setup.ts" },
});
