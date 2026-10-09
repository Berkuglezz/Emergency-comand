import { Inbox, type LucideIcon, RotateCw, TriangleAlert } from "lucide-react"
import { type ReactNode, useId } from "react"
import { useTranslation } from "react-i18next"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export type PanelStatus = "ready" | "loading" | "empty" | "error"

interface PanelProps {
  title: string
  description?: string
  /** Acciones de cabecera (botones pequeños). */
  actions?: ReactNode
  status?: PanelStatus
  empty?: { icon?: LucideIcon; title?: string; description?: string }
  error?: { title?: string; description?: string; onRetry?: () => void }
  children?: ReactNode
  /** Sin relleno en el cuerpo: para listas que llegan hasta los bordes. */
  flush?: boolean
  className?: string
}

/**
 * Contenedor de una zona del centro de mando (lista, mapa, detalle…).
 * Gestiona los estados de carga, vacío y error de forma uniforme.
 */
export function Panel({
  title,
  description,
  actions,
  status = "ready",
  empty,
  error,
  children,
  flush = false,
  className,
}: PanelProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const EmptyIcon = empty?.icon ?? Inbox

  return (
    <section
      aria-labelledby={titleId}
      aria-busy={status === "loading"}
      data-status={status}
      className={cn("flex min-h-0 flex-col rounded-lg border bg-card", className)}
    >
      <header className="flex min-h-10 items-center justify-between gap-2 border-b px-3 py-1.5">
        <div className="flex min-w-0 flex-col">
          <h2 id={titleId} className="truncate text-sm font-semibold">
            {title}
          </h2>
          {description && <p className="truncate text-xs text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-1">{actions}</div>}
      </header>

      <div
        className={cn(
          // `relative`: lo posicionado dentro (p. ej. `sr-only`) se desplaza con
          // el panel en lugar de alargar la página.
          "relative flex min-h-0 flex-1 flex-col overflow-auto",
          // Los estados de carga, vacío y error conservan siempre el relleno.
          flush && status === "ready" ? "p-0" : "p-3"
        )}
      >
        {status === "loading" && (
          <div role="status" className="flex flex-col gap-2">
            <Skeleton className="h-row w-full" />
            <Skeleton className="h-row w-full" />
            <Skeleton className="h-row w-3/4" />
            <span className="sr-only">{t("common.loading")}</span>
          </div>
        )}

        {status === "empty" && (
          <Empty className="border border-dashed">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <EmptyIcon aria-hidden />
              </EmptyMedia>
              <EmptyTitle>{empty?.title ?? t("ops.panel.emptyTitle")}</EmptyTitle>
              {empty?.description && <EmptyDescription>{empty.description}</EmptyDescription>}
            </EmptyHeader>
          </Empty>
        )}

        {status === "error" && (
          <Alert variant="destructive">
            <TriangleAlert aria-hidden />
            <AlertTitle>{error?.title ?? t("ops.panel.errorTitle")}</AlertTitle>
            <AlertDescription>
              <p>{error?.description ?? t("ops.panel.errorDescription")}</p>
              {error?.onRetry && (
                <Button variant="outline" size="sm" className="mt-2" onClick={error.onRetry}>
                  <RotateCw data-icon="inline-start" aria-hidden />
                  {t("common.retry")}
                </Button>
              )}
            </AlertDescription>
          </Alert>
        )}

        {status === "ready" && children}
      </div>
    </section>
  )
}
