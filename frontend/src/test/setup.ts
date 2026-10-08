import "@testing-library/jest-dom/vitest"
import "@/i18n/config"

import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

import { clearAccessToken } from "@/lib/api-client"

afterEach(() => {
  cleanup()
  // El token vive en una variable de módulo: se limpia entre tests.
  clearAccessToken()
  localStorage.clear()
  sessionStorage.clear()
})
