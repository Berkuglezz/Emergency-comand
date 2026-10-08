import "@testing-library/jest-dom/vitest"
import "@/i18n/config"

import { cleanup } from "@testing-library/react"
import { afterEach, vi } from "vitest"

import { clearAccessToken } from "@/lib/api-client"

import { Map as FakeMap } from "./fake-maplibre"

// jsdom no tiene WebGL: MapLibre se sustituye por un doble en todos los tests.
vi.mock("maplibre-gl", () => import("./fake-maplibre"))

afterEach(() => {
  cleanup()
  // El token vive en una variable de módulo: se limpia entre tests.
  clearAccessToken()
  localStorage.clear()
  sessionStorage.clear()
  FakeMap.reset()
})
