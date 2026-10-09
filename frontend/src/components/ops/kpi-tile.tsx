import { TriangleAlert } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Skeleton } from "@/components/ui/skeleton"
import { formatNumber } from "@/lib/format"
import { cn } from "@/lib/utils"

import { TONE_ICONS, TONE_STYLES, type Tone } from "./tones"

export type KpiTileState = "ready" | "loading" | "error"

interface KpiTileProps {
  label: string
  /** `null` o `undefined`: sin dato (se muestra «—»). */
  value?: number | null
  unit?: string
  /** Estado que comunica la cifra; añade icono y color. */
  tone?: Tone
  state?: KpiTileState
  /** `compact`: una sola línea (etiqueta y cifra), para franjas de indicadores. */
  variant?: "default" | "compact"
  className?: string
}

/** Indicador numérico compacto. Sin datos falsos: si no hay valor, lo dice. */
export function KpiTile({
  label,
  value,
  unit,
  tone,
  state = "ready",
  variant = "default",
  className,
}: KpiTileProps) {
  const { t } = useTranslation()
  const ToneIcon = tone ? TONE_ICONS[tone] : null

  if (variant === "compact") {
    return (
      <div
        data-state={state}
        aria-busy={state === "loading"}
        className={cn(
          "flex h-8 shrink-0 items-center gap-2 rounded-md border bg-card px-2.5",
          className
        )}
      >
        <span className="text-xs whitespace-nowrap text-muted-foreground">{label}</span>
        {state === "loading" && (
          <span role="status" className="flex items-center">
            <Skeleton className="h-4 w-6" />
            <span className="sr-only">{t("common.loading")}</span>
          </span>
        )}
        {state === "error" && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <TriangleAlert aria-hidden className="size-3.5" />
            {t("ops.kpi.unavailable")}
          </span>
        )}
        {state === "ready" && (
          <span className={cn("flex items-center gap-1", tone && TONE_STYLES[tone].text)}>
            {ToneIcon && <ToneIcon aria-hidden className="size-3.5" />}
            {value === null || value === undefined ? (
              <>
                <span aria-hidden className="font-data text-muted-foreground">
                  —
                </span>
                <span className="sr-only">{t("common.noData")}</span>
              </>
            ) : (
              <span className="font-data text-sm font-semibold">
                {formatNumber(value)}
                {unit && <span className="ml-0.5 text-xs font-normal">{unit}</span>}
              </span>
            )}
          </span>
        )}
      </div>
    )
  }

  return (
    <div
      data-state={state}
      aria-busy={state === "loading"}
      className={cn("flex min-w-36 flex-col gap-1 rounded-lg border bg-card px-3 py-2", className)}
    >
      <span className="text-xs font-medium text-muted-foreground">{label}</span>

      {state === "loading" && (
        <div role="status" className="flex h-8 items-center">
          <Skeleton className="h-6 w-16" />
          <span className="sr-only">{t("common.loading")}</span>
        </div>
      )}

      {state === "error" && (
        <div className="flex h-8 items-center gap-1.5 text-muted-foreground">
          <TriangleAlert aria-hidden className="size-4" />
          <span>{t("ops.kpi.unavailable")}</span>
        </div>
      )}

      {state === "ready" && (
        <div className={cn("flex h-8 items-center gap-1.5", tone && TONE_STYLES[tone].text)}>
          {ToneIcon && <ToneIcon aria-hidden className="size-5" />}
          {value === null || value === undefined ? (
            <>
              <span aria-hidden className="font-data text-2xl text-muted-foreground">
                —
              </span>
              <span className="sr-only">{t("common.noData")}</span>
            </>
          ) : (
            <span className="font-data text-3xl leading-none font-semibold">
              {formatNumber(value)}
              {unit && <span className="ml-1 text-sm font-normal">{unit}</span>}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
