import { render } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { createMemoryRouter, RouterProvider } from "react-router"

import { AppProviders } from "@/app/providers"
import { createQueryClient } from "@/app/query-client"
import { routes } from "@/app/router"

/** Renderiza la aplicación real (rutas, proveedores) en una ruta inicial. */
export function renderApp(initialPath = "/", { retry = true }: { retry?: boolean } = {}) {
  const queryClient = createQueryClient()
  if (!retry) {
    // Sin reintentos con espera: los estados de error aparecen al momento.
    queryClient.setDefaultOptions({
      ...queryClient.getDefaultOptions(),
      queries: { ...queryClient.getDefaultOptions().queries, retry: false },
    })
  }
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })
  const user = userEvent.setup()
  const view = render(
    <AppProviders queryClient={queryClient}>
      <RouterProvider router={router} />
    </AppProviders>
  )
  return { ...view, router, queryClient, user }
}
