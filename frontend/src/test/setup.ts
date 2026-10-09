import "@testing-library/jest-dom/vitest"
import "@/i18n/config"

import { cleanup } from "@testing-library/react"
import { afterEach, vi } from "vitest"

import { clearAccessToken } from "@/lib/api-client"

import { Map as FakeMap } from "./fake-maplibre"

// La app carga páginas y mapas en diferido (`lazy`). Se precargan aquí para que
// el primer test de cada fichero no pague la carga en frío del módulo dentro de
// la espera de Testing Library (no es lentitud de la app ni del test).
await Promise.all([
  import("@/features/auth/components/login-page"),
  import("@/features/command-center/components/command-center-page"),
  import("@/features/incidents/components/incidents-page"),
  import("@/features/incidents/components/incident-detail-page"),
  import("@/features/incidents/components/new-incident-page"),
  import("@/features/resources/components/resources-page"),
  import("@/features/resources/components/resource-detail-page"),
  import("@/features/resources/components/new-resource-page"),
  import("@/features/organizations/components/organizations-page"),
  import("@/features/map/incidents-map"),
  import("@/features/map/point-map"),
])

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
