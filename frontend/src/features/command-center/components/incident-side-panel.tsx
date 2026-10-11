import { useQueryClient } from "@tanstack/react-query"
import { ExternalLink, MousePointerClick, X } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Link, useLocation } from "react-router"

import { DateTimeText, DetailItem } from "@/components/ops/detail-item"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Button, buttonVariants } from "@/components/ui/button"
import { AssignmentsPanel } from "@/features/assignments/components/assignments-panel"
import { hasPermission, useSession } from "@/features/auth/hooks"
import {
  IncidentStatusPill,
  IncidentTypeLabel,
} from "@/features/incidents/components/incident-badges"
import { IncidentStatusActions } from "@/features/incidents/components/incident-status-actions"
import { TimelineEntry } from "@/features/incidents/components/incident-timeline"
import { CoordinatesText } from "@/features/incidents/components/location-text"
import { useIncident, useIncidentEvents } from "@/features/incidents/hooks"
import { incidentErrorMessage } from "@/features/incidents/presentation"
import { PerimetersPanel } from "@/features/map-features/components/perimeters-panel"
import { formatNumber } from "@/lib/format"
import { returnState } from "@/lib/navigation"
import { queryKeys } from "@/lib/query-keys"

import { DockToggle } from "./dock"

const LAST_EVENTS = 5

interface IncidentSidePanelProps {
  incidentId: string | null
  onClose: () => void
  /** Pliega la columna lateral (el incidente sigue seleccionado). */
  onCollapse: () => void
}

/**
 * Incidente seleccionado sin salir del centro de mando: resumen, acciones de
 * estado, recursos asignados (asignar, reasignar, llegada y retirada),
 * perímetros dibujados (solo lectura) y últimos eventos. Son los mismos
 * componentes que la ficha completa, con las mismas comprobaciones de permisos (y el backend vuelve a comprobarlo todo).
 */
export function IncidentSidePanel({ incidentId, onClose, onCollapse }: IncidentSidePanelProps) {
  const { t } = useTranslation()
  const toggle = (
    <DockToggle
      side="right"
      open
      label={t("commandCenter.dock.detail")}
      onOpenChange={onCollapse}
    />
  )

  if (!incidentId) {
    return (
      <Panel title={t("commandCenter.detail.title")} actions={toggle}>
        <p className="flex items-center gap-2 text-muted-foreground">
          <MousePointerClick aria-hidden className="size-4 shrink-0" />
          {t("commandCenter.detail.empty")}
        </p>
      </Panel>
    )
  }
  // `key`: al cambiar de selección se reinicia el panel con el nuevo incidente.
  return <SelectedIncident key={incidentId} id={incidentId} onClose={onClose} toggle={toggle} />
}

function SelectedIncident({
  id,
  onClose,
  toggle,
}: {
  id: string
  onClose: () => void
  toggle: ReactNode
}) {
  const { t } = useTranslation()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { data: user } = useSession()
  const incident = useIncident(id)
  const events = useIncidentEvents(id)

  // Recarga el incidente y su historial (p. ej. tras un 409 `version_conflict`).
  const reload = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.incident(id) })
  }

  let status: PanelStatus = "ready"
  if (incident.isPending) status = "loading"
  else if (incident.isError) status = "error"
  const data = incident.data
  const canChangeStatus = hasPermission(user, "incidents:change_status")
  // Lo más reciente primero: en el panel interesa qué acaba de pasar.
  const lastEvents = (events.data ?? []).slice(-LAST_EVENTS).reverse()

  return (
    <>
      <Panel
        title={t("commandCenter.detail.title")}
        actions={
          <>
            {data && (
              /* «Volver» desde la ficha regresa al centro de mando con esta selección. */
              <Link
                to={`/incidents/${data.id}`}
                state={returnState(location)}
                aria-label={t("commandCenter.detail.open")}
                title={t("commandCenter.detail.open")}
                className={buttonVariants({ variant: "ghost", size: "icon-sm" })}
              >
                <ExternalLink aria-hidden />
              </Link>
            )}
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("commandCenter.detail.close")}
              title={t("commandCenter.detail.close")}
              onClick={onClose}
            >
              <X aria-hidden />
            </Button>
            {toggle}
          </>
        }
        status={status}
        error={{
          description: incidentErrorMessage(incident.error, t),
          onRetry: () => void incident.refetch(),
        }}
      >
        {data && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-data font-semibold">{data.code}</span>
                <PriorityBadge priority={data.priority} pulse={data.closed_at === null} />
                <IncidentStatusPill status={data.status} />
                {data.is_simulated && <SimulatedPill />}
              </div>
              <h3 className="font-semibold">{data.title}</h3>
              <IncidentTypeLabel type={data.type} className="text-muted-foreground" />
            </div>

            {canChangeStatus && (
              <IncidentStatusActions
                incident={data}
                canClose={hasPermission(user, "incidents:close")}
                onReload={reload}
              />
            )}

            <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
              <DetailItem label={t("incidents.fields.municipality")}>
                {data.location.municipality}
              </DetailItem>
              <DetailItem label={t("incidents.fields.coordinates")}>
                <CoordinatesText location={data.location} />
              </DetailItem>
              <DetailItem label={t("incidents.fields.affectedPeople")}>
                {data.affected_people === null ? "—" : formatNumber(data.affected_people)}
              </DetailItem>
              <DetailItem label={t("incidents.fields.reportedAt")}>
                <DateTimeText value={data.reported_at} />
              </DetailItem>
              <DetailItem label={t("incidents.fields.updatedAt")}>
                <DateTimeText value={data.updated_at} />
              </DetailItem>
            </dl>
          </div>
        )}
      </Panel>

      {data && <AssignmentsPanel incident={data} onReload={reload} />}

      {data && <PerimetersPanel incidentId={data.id} />}

      {data && (
        <Panel title={t("commandCenter.detail.lastEvents")}>
          {events.isError ? (
            <p className="text-muted-foreground">{incidentErrorMessage(events.error, t)}</p>
          ) : (
            <ol className="flex flex-col">
              {lastEvents.map((event) => (
                <TimelineEntry key={event.id} event={event} />
              ))}
            </ol>
          )}
        </Panel>
      )}
    </>
  )
}
