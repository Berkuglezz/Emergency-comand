import { PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

type DockSide = "left" | "right"

interface DockToggleProps {
  side: DockSide
  open: boolean
  /** Nombre del panel, para el texto accesible («Plegar Incidentes activos»). */
  label: string
  onOpenChange: (open: boolean) => void
}

/** Botón de plegar/desplegar un panel lateral del centro de mando. */
export function DockToggle({ side, open, label, onOpenChange }: DockToggleProps) {
  const { t } = useTranslation()
  const Icon =
    side === "left"
      ? open
        ? PanelLeftClose
        : PanelLeftOpen
      : open
        ? PanelRightClose
        : PanelRightOpen
  const text = open
    ? t("commandCenter.dock.collapse", { panel: label })
    : t("commandCenter.dock.expand", { panel: label })
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      aria-expanded={open}
      aria-label={text}
      title={text}
      onClick={() => {
        onOpenChange(!open)
      }}
    >
      <Icon aria-hidden />
    </Button>
  )
}

interface DockProps extends DockToggleProps {
  /** Anchuras del panel desplegado (por tamaño de pantalla). */
  widthClassName: string
  /** Resumen visible con el panel plegado (p. ej. un recuento). */
  summary?: ReactNode
  children: ReactNode
}

/**
 * Columna lateral plegable. Plegada queda en un carril estrecho con el botón
 * para desplegarla; el mapa, a su lado, recupera de verdad el espacio (no se
 * superpone). El contenido plegado no se monta.
 */
export function Dock({
  side,
  open,
  label,
  onOpenChange,
  widthClassName,
  summary,
  children,
}: DockProps) {
  return (
    <div
      data-dock={side}
      data-open={open}
      className={cn(
        "flex min-h-0 w-full shrink-0 flex-col transition-[width] duration-150 ease-out motion-reduce:transition-none",
        open ? widthClassName : "lg:w-10",
        // En pantallas estrechas las columnas se apilan; el mapa va en medio.
        side === "left" ? "order-1" : "order-3"
      )}
    >
      {open ? (
        children
      ) : (
        <div className="flex items-center gap-2 rounded-lg border bg-card p-1 lg:h-full lg:flex-col">
          <DockToggle side={side} open={false} label={label} onOpenChange={onOpenChange} />
          <span className="truncate text-xs font-medium text-muted-foreground lg:rotate-180 lg:[writing-mode:vertical-rl]">
            {label}
          </span>
          {summary}
        </div>
      )}
    </div>
  )
}
