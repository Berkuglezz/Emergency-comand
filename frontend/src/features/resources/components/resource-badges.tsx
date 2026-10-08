import {
  Ambulance,
  CircleHelp,
  CircleOff,
  type LucideIcon,
  Package,
  RadioTower,
  Shield,
  Truck,
  Wrench,
} from "lucide-react"
import { useTranslation } from "react-i18next"

import { StatusPill } from "@/components/ops/status-pill"
import { useCodeLabel } from "@/lib/code-label"
import { cn } from "@/lib/utils"

import { RESOURCE_STATUS_ICONS, RESOURCE_STATUS_TONE } from "../presentation"
import type { ResourceStatus } from "../types"

export function ResourceStatusPill({ status }: { status: ResourceStatus }) {
  const { t } = useTranslation()
  return (
    <StatusPill tone={RESOURCE_STATUS_TONE[status]} icon={RESOURCE_STATUS_ICONS[status]}>
      <span className="sr-only">{t("resourceStatus.label")}: </span>
      {t(`resourceStatus.${status}`)}
    </StatusPill>
  )
}

/** Recurso desactivado (`is_active = false`): no opera hasta que se reactive. */
export function DeactivatedPill() {
  const { t } = useTranslation()
  return (
    <StatusPill tone="inactive" icon={CircleOff}>
      {t("resources.deactivated")}
    </StatusPill>
  )
}

/*
 * Iconos de Lucide que usa el catálogo `resource_types.icon`, importados uno a
 * uno para no inflar el bundle. Un icono desconocido muestra uno genérico.
 */
const TYPE_ICONS: Record<string, LucideIcon> = {
  Truck,
  Wrench,
  Ambulance,
  RadioTower,
  Shield,
  Package,
}

export function ResourceTypeLabel({
  type,
  className,
}: {
  type: { code: string; icon: string }
  className?: string
}) {
  const label = useCodeLabel()
  const Icon = TYPE_ICONS[type.icon] ?? CircleHelp
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-1.5", className)}>
      <Icon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
      <span className="truncate">{label("resourceTypes", type.code)}</span>
    </span>
  )
}
