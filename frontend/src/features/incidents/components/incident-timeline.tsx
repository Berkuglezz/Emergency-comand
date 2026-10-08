import type { TFunction } from "i18next"
import { History } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Panel, type PanelStatus } from "@/components/ops/panel"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { formatCoordinates, formatDateTime } from "@/lib/format"
import { type CodeGroup, useCodeLabel } from "@/lib/code-label"
import { cn } from "@/lib/utils"

import { useIncidentEvents } from "../hooks"
import { EVENT_ICONS, incidentErrorMessage, STATUS_CODES } from "../presentation"
import type { IncidentEvent } from "../types"
import { NoteForm } from "./note-form"

interface IncidentTimelineProps {
  incidentId: string
  canAddNotes: boolean
  className?: string
}

/** Historial funcional del incidente, en orden cronológico, y alta de notas. */
export function IncidentTimeline({ incidentId, canAddNotes, className }: IncidentTimelineProps) {
  const { t } = useTranslation()
  const events = useIncidentEvents(incidentId)

  let status: PanelStatus = "ready"
  if (events.isPending) status = "loading"
  else if (events.isError) status = "error"
  else if (events.data.length === 0) status = "empty"

  return (
    <div className={cn("flex min-h-0 flex-col gap-3", className)}>
      <Panel
        title={t("incidents.timeline.title")}
        status={status}
        empty={{ icon: History, description: t("incidents.timeline.empty") }}
        error={{
          description: incidentErrorMessage(events.error, t),
          onRetry: () => void events.refetch(),
        }}
        className="min-h-0 flex-1"
      >
        <ol className="flex flex-col">
          {events.data?.map((event) => (
            <TimelineEntry key={event.id} event={event} />
          ))}
        </ol>
      </Panel>
      {/* Fuera del panel: se puede anotar aunque el historial esté cargando o falle. */}
      {canAddNotes && <NoteForm incidentId={incidentId} />}
    </div>
  )
}

export function TimelineEntry({ event }: { event: IncidentEvent }) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const Icon = EVENT_ICONS[event.event_type]
  const { text, detail } = describeEvent(event, t, label)

  return (
    <li className="flex gap-2 border-l py-1.5 pl-3 first:pt-0 last:pb-0">
      <Icon aria-hidden className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
      <div className="flex min-w-0 flex-col">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <time dateTime={event.occurred_at} className="font-data text-xs text-muted-foreground">
            {formatDateTime(event.occurred_at)}
          </time>
          <span className="text-xs text-muted-foreground">
            {event.actor?.full_name ?? t("common.system")}
          </span>
        </div>
        <p className="font-medium">{text}</p>
        {detail && (
          <p className="break-words whitespace-pre-line text-muted-foreground">{detail}</p>
        )}
      </div>
    </li>
  )
}

// --- Texto de cada entrada --------------------------------------------------------

/** «Municipio · descripción · lat, lon» de un `location_changed` (antes o después). */
function describeLocation(value: unknown, t: TFunction): string {
  if (typeof value !== "object" || value === null) return "—"
  const location = value as Record<string, unknown>
  const latitude = location.latitude
  const longitude = location.longitude
  return [
    text(location.municipality) ?? "—",
    text(location.description),
    typeof latitude === "number" && typeof longitude === "number"
      ? formatCoordinates(latitude, longitude)
      : t("incidents.location.noCoordinates"),
  ]
    .filter(Boolean)
    .join(" · ")
}

function text(value: unknown): string | null {
  return typeof value === "string" && value ? value : null
}

/**
 * Compone la frase traducida a partir de los códigos del `payload` (la API
 * nunca devuelve textos). Un código desconocido se muestra tal cual.
 */
function describeEvent(
  event: IncidentEvent,
  t: TFunction,
  label: (group: CodeGroup, code: string) => string
): { text: string; detail: string | null } {
  const payload = event.payload
  const fields = (group: CodeGroup) =>
    (Array.isArray(payload.fields) ? payload.fields : [])
      .filter((field): field is string => typeof field === "string")
      .map((field) => label(group, field))
      .join(", ")
  const status = (value: unknown) => {
    const code = text(value)
    return code && (STATUS_CODES as string[]).includes(code)
      ? t(`incidentStatus.${code as (typeof STATUS_CODES)[number]}`)
      : (code ?? "—")
  }
  const priority = (value: unknown) => {
    const code = text(value)
    return code && (PRIORITY_CODES as string[]).includes(code)
      ? t(`priority.${code as (typeof PRIORITY_CODES)[number]}`)
      : (code ?? "—")
  }

  switch (event.event_type) {
    case "incident_created": {
      const parent = text(payload.parent)
      return {
        text: parent
          ? t("incidents.timeline.createdInParent", {
              priority: priority(payload.priority),
              parent,
            })
          : t("incidents.timeline.created", { priority: priority(payload.priority) }),
        detail: null,
      }
    }
    case "status_changed": {
      const reason = text(payload.reason)
      return {
        text: t("incidents.timeline.statusChanged", {
          from: status(payload.from),
          to: status(payload.to),
        }),
        detail: reason ? t("incidents.timeline.reason", { reason }) : null,
      }
    }
    case "priority_changed":
      return {
        text: t("incidents.timeline.priorityChanged", {
          from: priority(payload.from),
          to: priority(payload.to),
        }),
        detail: null,
      }
    case "incident_updated":
      return {
        text: t("incidents.timeline.updated", { fields: fields("incidentFields") }),
        detail: null,
      }
    case "location_changed":
      return {
        text: t("incidents.timeline.locationChanged", { fields: fields("locationFields") }),
        detail: t("incidents.timeline.locationFromTo", {
          from: describeLocation(payload.from, t),
          to: describeLocation(payload.to, t),
        }),
      }
    case "note_added":
      return { text: t("incidents.timeline.noteAdded"), detail: text(payload.text) }
    case "parent_changed": {
      const from = text(payload.from)
      const to = text(payload.to)
      if (from && to)
        return { text: t("incidents.timeline.parentMoved", { from, to }), detail: null }
      if (to) return { text: t("incidents.timeline.parentSet", { to }), detail: null }
      return { text: t("incidents.timeline.parentRemoved", { from: from ?? "—" }), detail: null }
    }
  }
}
