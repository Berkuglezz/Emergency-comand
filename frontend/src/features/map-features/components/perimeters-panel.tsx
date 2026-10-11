import { Shapes } from "lucide-react"
import { useTranslation } from "react-i18next"

import { DateTimeText } from "@/components/ops/detail-item"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { StatusPill } from "@/components/ops/status-pill"
import { incidentErrorMessage } from "@/features/incidents/presentation"

import { useIncidentPerimeters } from "../hooks"

/**
 * Perímetros guardados del incidente (mapa operativo, CLAUDE.md §2.12, M.2).
 * Solo lectura: ni dibujar, ni editar, ni retirar. Todo lo dibujado es
 * «Dibujado · no validado» (D-M5).
 */
export function PerimetersPanel({ incidentId }: { incidentId: string }) {
  const { t } = useTranslation()
  const perimeters = useIncidentPerimeters(incidentId)

  let status: PanelStatus = "ready"
  if (perimeters.isPending) status = "loading"
  else if (perimeters.isError) status = "error"
  else if (perimeters.data.length === 0) status = "empty"

  return (
    <Panel
      title={t("mapFeatures.perimeters.title")}
      status={status}
      empty={{ icon: Shapes, description: t("mapFeatures.perimeters.empty") }}
      error={{
        description: incidentErrorMessage(perimeters.error, t),
        onRetry: () => void perimeters.refetch(),
      }}
    >
      <ul className="flex flex-col gap-2">
        {perimeters.data?.map((feature) => {
          const { properties } = feature
          const author = properties.updated_by ?? properties.created_by
          return (
            <li key={feature.id} className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span
                  aria-hidden
                  className="size-3.5 shrink-0 rounded-sm border-2 border-dashed border-warning bg-warning-subtle"
                />
                <span className="font-medium">
                  {properties.label ?? t("mapFeatures.perimeters.unlabeled")}
                </span>
                <StatusPill tone="warning" icon={Shapes}>
                  {t("mapFeatures.unverified")}
                </StatusPill>
                {properties.is_simulated && <SimulatedPill />}
              </div>
              {properties.note && <p className="text-muted-foreground">{properties.note}</p>}
              <p className="text-xs text-muted-foreground">
                {t("mapFeatures.perimeters.updated", {
                  author: author?.full_name ?? t("common.system"),
                })}{" "}
                <DateTimeText value={properties.updated_at} />
              </p>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
