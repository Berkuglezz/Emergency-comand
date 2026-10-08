/// <reference types="vitest/config" />
import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// En Docker Compose el backend es `http://backend:8000`; en local, localhost.
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    // El navegador solo habla con Vite: /api se redirige al backend, así la
    // cookie del refresh token es del mismo origen.
    proxy: {
      "/api": { target: apiProxyTarget },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    // Ningún test habla con el backend real: `fetch` se sustituye en cada test.
    restoreMocks: true,
    unstubGlobals: true,
  },
})
