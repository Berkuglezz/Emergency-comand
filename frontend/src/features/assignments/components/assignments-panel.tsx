import { CircleCheck, LogOut, MapPinCheck, Plus, Truck } from "lucide-react"
import { useId, useState } from "react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import { ConfirmDialog } from "@/components/ops/confirm-dialog"
import { DateTimeText } from "@/components/ops/detail-item"
import { EtaText } from "@/components/ops/eta-text"
import { MutationErrorAlert } from "@/components/ops/mutation-error-alert"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { hasPermission, useSession } from "@/features/auth/hooks"
import type { IncidentDetail } from "@/features/incidents/types"
import { ResourceTypeLabel } from "@/features/resources/components/resource-badges"

import { useAssignments, useMarkArrival, useReleaseResource } from "../hooks"
import { assignmentErrorMessage, USER_RELEASE_REASONS } from "../presentation"
import type { Assignment, ReleaseReason } from "../types"
import { AssignDialog } from "./assign-dialog"

/** Recurso asignado: código, tipo, organización, estado de la asignación y ETA estimada. */
export function AssignmentSummary({ assignment }: { assignment: Assignment }) {
  const { t } = useTranslation()
  const { resource } = assignment
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Link
          to={`/resources/${resource.id}`}
          className="font-data font-medium underline-offset-4 hover:underline"
        >
          {resource.code}
        </Link>
        <ResourceTypeLabel type={resource.type} className="text-muted-foreground" />
        {resource.is_simulated && <SimulatedPill />}
      </div>
      <span className="truncate text-xs text-muted-foreground">
        {resource.name} · {resource.organization.name}
      </span>
      <span className="flex flex-wrap items-center gap-x-2 text-xs">
        {assignment.released_at ? (
          <span className="text-muted-foreground">
            {t("assignments.released", {
              reason: t(`assignments.reasons.${assignment.release_reason ?? "completed"}`),
            })}{" "}
            <DateTimeText value={assignment.released_at} />
          </span>
        ) : assignment.arrived_at ? (
          <span className="inline-flex items-center gap-1 text-ok">
            <CircleCheck aria-hidden className="size-3.5" />
            {t("assignments.onScene")}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-info">
            <Truck aria-hidden className="size-3.5" />
            {t("assignments.enRoute")}
          </span>
        )}
        {!assignment.released_at && !assignment.arrived_at && (
          <EtaText eta={assignment.eta} assignedAt={assignment.assigned_at} />
        )}
      </span>
    </div>
  )
}

interface AssignmentsPanelProps {
  incident: IncidentDetail
  onReload: () => void
}

/**
 * Recursos asignados al incidente (activos e historial). Asignar y retirar
 * exigen `assignments:manage`; marcar la llegada, `assignments:update`. El
 * backend vuelve a comprobarlo todo.
 */
export function AssignmentsPanel({ incident, onReload }: AssignmentsPanelProps) {
  const { t } = useTranslation()
  const id = useId()
  const { data: user } = useSession()
  const assignments = useAssignments(incident.id)
  const arrival = useMarkArrival()
  const release = useReleaseResource()
  const [assigning, setAssigning] = useState(false)
  const [releasing, setReleasing] = useState<Assignment | null>(null)
  const [reason, setReason] = useState<ReleaseReason | "">("")

  const open = incident.closed_at === null
  const canManage = open && hasPermission(user, "assignments:manage")
  const canUpdate = open && hasPermission(user, "assignments:update")
  const active = (assignments.data ?? []).filter((a) => a.released_at === null)
  const history = (assignments.data ?? []).filter((a) => a.released_at !== null)

  let status: PanelStatus = "ready"
  if (assignments.isPending) status = "loading"
  else if (assignments.isError) status = "error"
  else if (assignments.data.length === 0) status = "empty"

  const failed = arrival.isError ? arrival : release.isError ? release : null

  return (
    <>
      <Panel
        title={t("assignments.title")}
        description={t("assignments.count", { count: active.length })}
        actions={
          canManage && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setAssigning(true)
              }}
            >
              <Plus data-icon="inline-start" aria-hidden />
              {t("assignments.assign")}
            </Button>
          )
        }
        status={status}
        empty={{ icon: Truck, description: t("assignments.empty") }}
        error={{
          description: assignmentErrorMessage(assignments.error, t),
          onRetry: () => void assignments.refetch(),
        }}
      >
        <div className="flex flex-col gap-3">
          {failed && (
            <MutationErrorAlert
              error={failed.error}
              message={assignmentErrorMessage(failed.error, t)}
              conflict={{
                title: t("incidents.detail.conflict.title"),
                description: t("incidents.detail.conflict.description"),
              }}
              onReload={() => {
                failed.reset()
                onReload()
              }}
            />
          )}
          {active.length > 0 && (
            <ul aria-label={t("assignments.active")} className="flex flex-col divide-y">
              {active.map((assignment) => (
                <li
                  key={assignment.id}
                  className="flex flex-wrap items-start gap-2 py-2 first:pt-0"
                >
                  <div className="min-w-0 flex-1">
                    <AssignmentSummary assignment={assignment} />
                  </div>
                  <div className="flex gap-1">
                    {canUpdate && !assignment.arrived_at && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={arrival.isPending}
                        aria-label={t("assignments.markArrivalFor", {
                          code: assignment.resource.code,
                        })}
                        onClick={() => {
                          release.reset()
                          arrival.mutate({ assignmentId: assignment.id, version: incident.version })
                        }}
                      >
                        <MapPinCheck data-icon="inline-start" aria-hidden />
                        {t("assignments.markArrival")}
                      </Button>
                    )}
                    {canManage && (
                      <Button
                        size="sm"
                        variant="outline"
                        aria-label={t("assignments.releaseFor", { code: assignment.resource.code })}
                        onClick={() => {
                          arrival.reset()
                          setReason("")
                          setReleasing(assignment)
                        }}
                      >
                        <LogOut data-icon="inline-start" aria-hidden />
                        {t("assignments.release")}
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {history.length > 0 && (
            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground">
                {t("assignments.history", { count: history.length })}
              </summary>
              <ul className="mt-2 flex flex-col divide-y">
                {history.map((assignment) => (
                  <li key={assignment.id} className="py-2 first:pt-0">
                    <AssignmentSummary assignment={assignment} />
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </Panel>

      {/* Fuera del panel: se pueden abrir aunque aún no haya asignaciones. */}
      {canManage && (
        <AssignDialog open={assigning} onOpenChange={setAssigning} incident={incident} />
      )}

      <ConfirmDialog
        open={releasing !== null}
        onOpenChange={(next) => {
          if (!next) setReleasing(null)
        }}
        pending={release.isPending}
        confirmDisabled={reason === ""}
        title={t("assignments.confirmRelease.title", { code: releasing?.resource.code ?? "" })}
        description={t("assignments.confirmRelease.description")}
        confirmLabel={t("assignments.release")}
        onConfirm={() => {
          if (!releasing || reason === "") return
          release.mutate(
            { assignmentId: releasing.id, body: { version: incident.version, reason } },
            {
              onSettled: () => {
                setReleasing(null)
              },
            }
          )
        }}
      >
        <Field>
          <FieldLabel htmlFor={`${id}-reason`}>{t("assignments.confirmRelease.reason")}</FieldLabel>
          <NativeSelect
            id={`${id}-reason`}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value as ReleaseReason | "")
            }}
          >
            <NativeSelectOption value="">
              {t("assignments.confirmRelease.selectReason")}
            </NativeSelectOption>
            {USER_RELEASE_REASONS.map((code) => (
              <NativeSelectOption key={code} value={code}>
                {t(`assignments.reasons.${code}`)}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Field>
      </ConfirmDialog>
    </>
  )
}
