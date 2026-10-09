import { Outlet, useMatch } from "react-router"

import { cn } from "@/lib/utils"

import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"

/** Layout de la aplicación: barra superior, barra lateral plegable y contenido. */
export function AppShell() {
  // El centro de mando ocupa toda la zona de trabajo y gestiona su propio
  // desplazamiento por panel; el resto de pantallas se desplazan como página.
  const isCommandCenter = useMatch({ path: "/", end: true }) !== null

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar />
        <main
          className={cn(
            "min-h-0 min-w-0 flex-1",
            isCommandCenter ? "overflow-auto p-2 lg:overflow-hidden" : "overflow-auto p-3"
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
