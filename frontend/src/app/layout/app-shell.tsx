import { Outlet } from "react-router"

import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"

/** Layout del centro de mando: barra lateral, barra superior y contenido. */
export function AppShell() {
  return (
    <div className="flex h-dvh overflow-hidden">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-auto p-3">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
