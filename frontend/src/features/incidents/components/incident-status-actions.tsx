import { useId, useState } from "react"
import { useTranslation } from "react-i18next"

import { ConfirmDialog } from "@/components/ops/confirm-dialog"
import { MutationErrorAlert } from "@/components/ops/mutation-error-alert"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import { useAssignments } from "@/features/assignments/hooks"

import { useChangeIncidentStatus } from "../hooks"
import { incidentErrorMessage, isIrreversible, STATUS_ICONS } from "../presentation"
import type { IncidentDetail, IncidentStatus } from "../types"

interface IncidentStatusActionsProps {
  incident: IncidentDetail
  /** Cerrar y cancelar exigen `incidents:close` (el backend lo comprueba). */
  canClose: boolean
  onReload: () => void
}

/**
 * Cambios de estado que el backend permite ahora (`allowed_transitions`): la
 * interfaz no duplica el flujo. Cerrar y cancelar piden confirmación.
 */
export function IncidentStatusActions({
  incident,
  canClose,
  onReload,
}: IncidentStatusActionsProps) {
  const { t } = useTranslation()
  const id = useId()
  const change = useChangeIncidentStatus(incident.id)
  const [confirming, setConfirming] = useState<IncidentStatus | null>(null)
  const [reason, setReason] = useState("")
  // Cerrar o cancelar retira los recursos asignados: la confirmación los enumera.
  const assignments = useAssignments(incident.id, {
    enabled: confirming !== null && incident.active_assignments > 0,
  })
  const toRelease = (assignments.data ?? []).filter((a) => a.released_at === null)

  const targets = incident.allowed_transitions.filter(
    (target) => !isIrreversible(target) || canClose
  )
  if (targets.length === 0) return null

  const apply = (status: IncidentStatus, withReason?: string) => {
    change.mutate(
      { status, version: incident.version, reason: withReason?.trim() ? withReason.trim() : null },
      {
        onSettled: () => {
          setConfirming(null)
          setReason("")
        },
      }
    )
  }

  const labelFor = (target: IncidentStatus) =>
    incident.status === "controlled" && target === "in_progress"
      ? t("incidents.actions.reopen")
      : t(`incidents.actions.toStatus.${target}`)

  return (
    <section aria-label={t("incidents.actions.label")} className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {targets.map((target) => {
          const Icon = STATUS_ICONS[target]
          const irreversible = isIrreversible(target)
          return (
            <Button
              key={target}
              variant={irreversible ? "destructive" : "outline"}
              disabled={change.isPending}
              onClick={() => {
                if (irreversible) setConfirming(target)
                else apply(target)
              }}
            >
              <Icon data-icon="inline-start" aria-hidden />
              {labelFor(target)}
            </Button>
          )
        })}
      </div>

      {change.isError && (
        <MutationErrorAlert
          error={change.error}
          message={incidentErrorMessage(change.error, t)}
          conflict={{
            title: t("incidents.detail.conflict.title"),
            description: t("incidents.detail.conflict.description"),
          }}
          onReload={() => {
            change.reset()
            onReload()
          }}
        />
      )}

      <ConfirmDialog
        open={confirming !== null}
        onOpenChange={(open) => {
          if (!open) {
            setConfirming(null)
            setReason("")
          }
        }}
        tone="destructive"
        pending={change.isPending}
        title={
          confirming === "cancelled"
            ? t("incidents.actions.confirm.cancelledTitle", { code: incident.code })
            : t("incidents.actions.confirm.closedTitle", { code: incident.code })
        }
        description={
          confirming === "cancelled"
            ? t("incidents.actions.confirm.cancelledDescription")
            : t("incidents.actions.confirm.closedDescription")
        }
        confirmLabel={confirming ? t(`incidents.actions.toStatus.${confirming}`) : ""}
        cancelLabel={t("incidents.actions.confirm.keep")}
        onConfirm={() => {
          if (confirming) apply(confirming, reason)
        }}
      >
        {incident.active_assignments > 0 && (
          <div className="flex flex-col gap-1 rounded-md border border-warning-border bg-warning-subtle p-2">
            <p className="font-medium">
              {t("incidents.actions.confirm.releases", { count: incident.active_assignments })}
            </p>
            <ul className="flex flex-wrap gap-x-3 font-data text-xs">
              {toRelease.map((assignment) => (
                <li key={assignment.id}>{assignment.resource.code}</li>
              ))}
            </ul>
          </div>
        )}
        <Field>
          <FieldLabel htmlFor={`${id}-reason`}>{t("incidents.actions.confirm.reason")}</FieldLabel>
          <Textarea
            id={`${id}-reason`}
            rows={2}
            maxLength={500}
            value={reason}
            placeholder={t("incidents.actions.confirm.reasonPlaceholder")}
            onChange={(event) => {
              setReason(event.target.value)
            }}
          />
        </Field>
      </ConfirmDialog>
    </section>
  )
}
