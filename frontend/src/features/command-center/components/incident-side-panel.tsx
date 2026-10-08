import { ExternalLink, PanelRight, X } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link, useLocation } from "react-router"

import { DateTimeText, DetailItem } from "@/components/ops/detail-item"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { PriorityBadge } from "@/components/ops/priority-badge"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  IncidentStatusPill,
  IncidentTypeLabel,
} from "@/features/incidents/components/incident-badges"
import { TimelineEntry } from "@/features/incidents/components/incident-timeline"
import { useIncident, useIncidentEvents } from "@/features/incidents/hooks"
import { incidentErrorMessage } from "@/features/incidents/presentation"
import { formatNumber } from "@/lib/format"
import { returnState } from "@/lib/navigation"

const LAST_EVENTS = 5

interface IncidentSidePanelProps {
  incidentId: string | null
  onClose: () => void
  className?: string
}

/** Resumen del incidente seleccionado y sus últimos eventos, sin salir del centro de mando. */
export function IncidentSidePanel({ incidentId, onClose, className }: IncidentSidePanelProps) {
  const { t } = useTranslation()

  if (!incidentId) {
    return (
      <Panel
        title={t("commandCenter.detail.title")}
        status="empty"
        empty={{ icon: PanelRight, description: t("commandCenter.detail.empty") }}
        className={className}
      />
    )
  }
  // `key`: al cambiar de selección se reinicia el panel con el nuevo incidente.
  return (
    <SelectedIncident key={incidentId} id={incidentId} onClose={onClose} className={className} />
  )
}

function SelectedIncident({
  id,
  onClose,
  className,
}: {
  id: string
  onClose: () => void
  className?: string
}) {
  const { t } = useTranslation()
  const location = useLocation()
  const incident = useIncident(id)
  const events = useIncidentEvents(id)

  let status: PanelStatus = "ready"
  if (incident.isPending) status = "loading"
  else if (incident.isError) status = "error"
  const data = incident.data
  // Lo más reciente primero: en el panel interesa qué acaba de pasar.
  const lastEvents = (events.data ?? []).slice(-LAST_EVENTS).reverse()

  return (
    <Panel
      title={t("commandCenter.detail.title")}
      actions={
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={t("commandCenter.detail.close")}
          onClick={onClose}
        >
          <X aria-hidden />
        </Button>
      }
      status={status}
      error={{
        description: incidentErrorMessage(incident.error, t),
        onRetry: () => void incident.refetch(),
      }}
      className={className}
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

          <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
            <DetailItem label={t("incidents.fields.municipality")}>{data.municipality}</DetailItem>
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

          <div className="flex flex-col gap-1.5">
            <h4 className="text-xs font-medium text-muted-foreground">
              {t("commandCenter.detail.lastEvents")}
            </h4>
            {events.isError ? (
              <p className="text-muted-foreground">{incidentErrorMessage(events.error, t)}</p>
            ) : (
              <ol className="flex flex-col">
                {lastEvents.map((event) => (
                  <TimelineEntry key={event.id} event={event} />
                ))}
              </ol>
            )}
          </div>

          {/* «Volver» desde la ficha regresa al centro de mando con esta selección. */}
          <Link
            to={`/incidents/${data.id}`}
            state={returnState(location)}
            className={buttonVariants({ variant: "outline" })}
          >
            <ExternalLink data-icon="inline-start" aria-hidden />
            {t("commandCenter.detail.open")}
          </Link>
        </div>
      )}
    </Panel>
  )
}
