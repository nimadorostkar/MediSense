import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During development, requests to /api are proxied to the local server
// (server/index.js) so the Anthropic API key never reaches the browser.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8787",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
