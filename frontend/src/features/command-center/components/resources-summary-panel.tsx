import { CircleOff, Truck } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import { Panel, type PanelStatus } from "@/components/ops/panel"
import { buttonVariants } from "@/components/ui/button"
import { ResourceStatusPill } from "@/features/resources/components/resource-badges"
import { RESOURCE_STATUS_CODES } from "@/features/resources/presentation"
import { formatNumber } from "@/lib/format"

import type { DashboardSummary } from "../types"

interface ResourcesSummaryPanelProps {
  summary: DashboardSummary["resources"] | undefined
  status: Exclude<PanelStatus, "empty">
  onRetry: () => void
}

/**
 * Recursos activos por estado (datos del resumen del backend). Cada fila abre el
 * listado filtrado. Sin asignaciones ni ubicación: llegan en fases posteriores.
 */
export function ResourcesSummaryPanel({ summary, status, onRetry }: ResourcesSummaryPanelProps) {
  const { t } = useTranslation()
  const panelStatus: PanelStatus =
    status === "ready" && summary?.active_total === 0 && summary.inactive_total === 0
      ? "empty"
      : status

  return (
    <Panel
      title={t("commandCenter.resources.title")}
      actions={
        <Link to="/resources" className={buttonVariants({ variant: "ghost", size: "sm" })}>
          {t("commandCenter.resources.viewAll")}
        </Link>
      }
      status={panelStatus}
      empty={{ icon: Truck, description: t("commandCenter.resources.empty") }}
      error={{ onRetry }}
    >
      <ul className="flex flex-col">
        {RESOURCE_STATUS_CODES.map((code) => (
          <li key={code}>
            <Link
              to={`/resources?status=${code}`}
              aria-label={t("commandCenter.resources.viewStatus", {
                status: t(`resourceStatus.${code}`),
              })}
              className="flex h-row items-center justify-between rounded-md px-1 hover:bg-muted/50"
            >
              <ResourceStatusPill status={code} />
              <span className="font-data text-base font-semibold">
                {formatNumber(summary?.by_status[code] ?? 0)}
              </span>
            </Link>
          </li>
        ))}
        {summary && summary.inactive_total > 0 && (
          <li className="flex h-row items-center justify-between px-1 text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <CircleOff aria-hidden className="size-4" />
              {t("resources.deactivated")}
            </span>
            <span className="font-data">{formatNumber(summary.inactive_total)}</span>
          </li>
        )}
      </ul>
    </Panel>
  )
}
