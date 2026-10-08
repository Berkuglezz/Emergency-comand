import {
  Biohazard,
  CarFront,
  CircleHelp,
  CloudLightning,
  Flame,
  FlameKindling,
  HeartPulse,
  LifeBuoy,
  type LucideIcon,
  Mountain,
  MountainSnow,
  Waves,
} from "lucide-react"
import { useTranslation } from "react-i18next"

import { StatusPill } from "@/components/ops/status-pill"
import { useCodeLabel } from "@/lib/code-label"
import { cn } from "@/lib/utils"

import { STATUS_ICONS, STATUS_TONE } from "../presentation"
import type { IncidentStatus } from "../types"

export function IncidentStatusPill({ status }: { status: IncidentStatus }) {
  const { t } = useTranslation()
  return (
    <StatusPill tone={STATUS_TONE[status]} icon={STATUS_ICONS[status]}>
      <span className="sr-only">{t("incidentStatus.label")}: </span>
      {t(`incidentStatus.${status}`)}
    </StatusPill>
  )
}

/*
 * Iconos de Lucide que usa el catálogo `incident_types.icon`. Se importan uno a
 * uno (no el paquete entero) para no inflar el bundle; un icono desconocido
 * muestra uno genérico.
 */
const TYPE_ICONS: Record<string, LucideIcon> = {
  Flame,
  FlameKindling,
  CarFront,
  HeartPulse,
  MountainSnow,
  LifeBuoy,
  Waves,
  CloudLightning,
  Biohazard,
  Mountain,
}

export function IncidentTypeLabel({
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
      <span className="truncate">{label("incidentTypes", type.code)}</span>
    </span>
  )
}
