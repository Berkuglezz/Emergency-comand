import { createBrowserRouter, type RouteObject } from "react-router"

import { AppShell } from "@/app/layout/app-shell"
import { NotFound } from "@/app/routes/not-found"
import { ProtectedRoute, RequirePermission } from "@/app/routes/protected-route"
import { RouteError } from "@/app/routes/route-error"
import { RouteLoading } from "@/app/routes/route-loading"

/*
 * Las páginas se cargan bajo demanda (`lazy`): el bundle inicial solo lleva el
 * núcleo (router, sesión, layout).
 *
 * Rutas solo de desarrollo. Con `import.meta.env.DEV` falso (build de
 * producción), Vite elimina la rama y el import dinámico: el catálogo no
 * llega al bundle. No aparecen en la navegación de la aplicación.
 */
const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [
      {
        path: "dev/design-system",
        lazy: async () => {
          const { DesignSystemPage } = await import("@/app/dev/design-system/design-system-page")
          return { Component: DesignSystemPage }
        },
      },
    ]
  : []

export const routes: RouteObject[] = [
  {
    path: "/",
    ErrorBoundary: RouteError,
    HydrateFallback: RouteLoading,
    children: [
      // Público
      {
        path: "login",
        lazy: async () => {
          const { LoginPage } = await import("@/features/auth/components/login-page")
          return { Component: LoginPage }
        },
      },
      ...devRoutes,

      // Protegido: todo lo demás exige sesión.
      {
        Component: ProtectedRoute,
        children: [
          {
            Component: AppShell,
            children: [
              {
                index: true,
                lazy: async () => {
                  const { CommandCenterPage } =
                    await import("@/features/command-center/components/command-center-page")
                  return { Component: CommandCenterPage }
                },
              },
              {
                path: "incidents",
                children: [
                  {
                    index: true,
                    lazy: async () => {
                      const { IncidentsPage } =
                        await import("@/features/incidents/components/incidents-page")
                      return {
                        element: (
                          <RequirePermission permission="incidents:read">
                            <IncidentsPage />
                          </RequirePermission>
                        ),
                      }
                    },
                  },
                  {
                    path: "new",
                    lazy: async () => {
                      const { NewIncidentPage } =
                        await import("@/features/incidents/components/new-incident-page")
                      return {
                        element: (
                          <RequirePermission permission="incidents:create">
                            <NewIncidentPage />
                          </RequirePermission>
                        ),
                      }
                    },
                  },
                  {
                    path: ":incidentId",
                    lazy: async () => {
                      const { IncidentDetailPage } =
                        await import("@/features/incidents/components/incident-detail-page")
                      return {
                        element: (
                          <RequirePermission permission="incidents:read">
                            <IncidentDetailPage />
                          </RequirePermission>
                        ),
                      }
                    },
                  },
                ],
              },
              {
                path: "resources",
                children: [
                  {
                    index: true,
                    lazy: async () => {
                      const { ResourcesPage } =
                        await import("@/features/resources/components/resources-page")
                      return {
                        element: (
                          <RequirePermission permission="resources:read">
                            <ResourcesPage />
                          </RequirePermission>
                        ),
                      }
                    },
                  },
                  {
                    path: "new",
                    lazy: async () => {
                      const { NewResourcePage } =
                        await import("@/features/resources/components/new-resource-page")
                      return {
                        element: (
                          <RequirePermission permission="resources:manage">
                            <NewResourcePage />
                          </RequirePermission>
                        ),
                      }
                    },
                  },
                  {
                    path: ":resourceId",
                    lazy: async () => {
                      const { ResourceDetailPage } =
                        await import("@/features/resources/components/resource-detail-page")
                      return {
                        element: (
                          <RequirePermission permission="resources:read">
                            <ResourceDetailPage />
                          </RequirePermission>
                        ),
                      }
                    },
                  },
                ],
              },
              {
                path: "organizations",
                lazy: async () => {
                  const { OrganizationsPage } =
                    await import("@/features/organizations/components/organizations-page")
                  return {
                    element: (
                      <RequirePermission permission="organizations:read">
                        <OrganizationsPage />
                      </RequirePermission>
                    ),
                  }
                },
              },
              { path: "*", Component: NotFound },
            ],
          },
        ],
      },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(routes)
}
