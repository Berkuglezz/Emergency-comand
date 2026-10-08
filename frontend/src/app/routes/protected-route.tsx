import { LoaderCircle, TriangleAlert } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Navigate, Outlet, useLocation } from "react-router"

import { Button } from "@/components/ui/button"
import { hasPermission, useSession, useSessionEndReason } from "@/features/auth/hooks"
import type { Permission } from "@/features/auth/types"

import { Forbidden } from "./forbidden"

function FullScreen({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3 p-6 text-center">
      {children}
    </main>
  )
}

/** Exige sesión. Sin sesión lleva al login recordando la ruta pedida. */
export function ProtectedRoute() {
  const { t } = useTranslation()
  const location = useLocation()
  const session = useSession()
  const endReason = useSessionEndReason()

  if (session.isPending) {
    return (
      <FullScreen>
        <div role="status" className="flex items-center gap-2 text-muted-foreground">
          <LoaderCircle aria-hidden className="size-4" />
          {t("auth.restoring")}
        </div>
      </FullScreen>
    )
  }

  if (session.isError) {
    return (
      <FullScreen>
        <div role="alert" className="flex flex-col items-center gap-2">
          <TriangleAlert aria-hidden className="size-5 text-critical" />
          <h1 className="text-base font-semibold">{t("auth.sessionCheckFailed.title")}</h1>
          <p className="text-muted-foreground">{t("auth.sessionCheckFailed.description")}</p>
          <Button variant="outline" onClick={() => void session.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      </FullScreen>
    )
  }

  if (!session.data) {
    // Tras un cierre de sesión explícito, el siguiente login empieza en el
    // centro de mando. Si la sesión caducó, se vuelve a la página en curso.
    const state = endReason === "logout" ? undefined : { from: location.pathname }
    return <Navigate to="/login" replace state={state} />
  }

  return <Outlet />
}

/** Oculta una ruta a quien no tiene el permiso. Solo UX: el backend responde 403. */
export function RequirePermission({
  permission,
  children,
}: {
  permission: Permission
  children: ReactNode
}) {
  const { data: user } = useSession()
  return hasPermission(user, permission) ? children : <Forbidden />
}
