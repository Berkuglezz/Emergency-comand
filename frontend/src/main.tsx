import "@/styles/index.css"

import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router/dom"

import { AppProviders } from "@/app/providers"
import { createQueryClient } from "@/app/query-client"
import { createAppRouter } from "@/app/router"
import i18n from "@/i18n/config"

document.title = i18n.t("app.name")

const rootElement = document.getElementById("root")
if (!rootElement) {
  throw new Error("No existe el elemento #root en index.html")
}

const queryClient = createQueryClient()
const router = createAppRouter()

createRoot(rootElement).render(
  <StrictMode>
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>
)
