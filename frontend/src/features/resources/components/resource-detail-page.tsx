import { useQueryClient } from "@tanstack/react-query"
import type { TFunction } from "i18next"
import { CircleOff, History, Link2, Lock, Pencil, Power } from "lucide-react"
import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Link, useParams } from "react-router"

import { BackLink } from "@/components/ops/back-link"
import { ConfirmDialog } from "@/components/ops/confirm-dialog"
import { DateTimeText, DetailItem } from "@/components/ops/detail-item"
import { EtaText } from "@/components/ops/eta-text"
import { MutationErrorAlert } from "@/components/ops/mutation-error-alert"
import { Panel } from "@/components/ops/panel"
import { SimulatedPill } from "@/components/ops/simulated-pill"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { canWriteOrganization, hasPermission, useSession } from "@/features/auth/hooks"
import { CoordinatesText } from "@/features/incidents/components/location-text"
import { useOrganizations } from "@/features/organizations/hooks"
import { ApiError } from "@/lib/api-client"
import { useCodeLabel } from "@/lib/code-label"
import { queryKeys } from "@/lib/query-keys"

import { resourceValuesFrom, toUpdatePayload } from "../form"
import { useChangeResourceStatus, useResource, useResourceTypes, useUpdateResource } from "../hooks"
import { RESOURCE_STATUS_CODES, RESOURCE_STATUS_ICONS, resourceErrorMessage } from "../presentation"
import type { Resource } from "../types"
import { DeactivatedPill, ResourceStatusPill, ResourceTypeLabel } from "./resource-badges"
import { ResourceForm } from "./resource-form"

function conflictTexts(t: TFunction) {
  return {
    title: t("resources.detail.conflict.title"),
    description: t("resources.detail.conflict.description"),
  }
}

/** Ficha de un recurso: estado operativo, datos y (con `resources:manage`) edición. */
export function ResourceDetailPage() {
  const { t } = useTranslation()
  const { resourceId = "" } = useParams()
  const queryClient = useQueryClient()
  const { data: user } = useSession()
  const resource = useResource(resourceId)

  const reload = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.resource(resourceId) })
  }

  if (resource.isPending || resource.isError) {
    const notFound =
      resource.error instanceof ApiError && [404, 422].includes(resource.error.status)
    return (
      <div className="flex flex-col gap-3">
        <BackLink fallback="/resources" />
        <Panel
          title={t("resources.detail.summary")}
          status={resource.isPending ? "loading" : "error"}
          error={{
            description: notFound
              ? t("resources.detail.notFound")
              : resourceErrorMessage(resource.error, t),
            onRetry: notFound ? undefined : () => void resource.refetch(),
          }}
        />
      </div>
    )
  }

  const data = resource.data
  const canManage = hasPermission(user, "resources:manage")

  return (
    <div className="flex max-w-5xl flex-col gap-3">
      <BackLink fallback="/resources" />
      <header className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-data text-base font-semibold">{data.code}</span>
          <ResourceStatusPill status={data.status} />
          {!data.is_active && <DeactivatedPill />}
          {data.is_simulated && <SimulatedPill />}
        </div>
        <h1 className="text-lg font-semibold">{data.name}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
          <ResourceTypeLabel type={data.type} />
          <span>{data.organization.name}</span>
          <span>{data.base.municipality}</span>
        </div>
      </header>

      {!data.is_active && (
        <Alert>
          <CircleOff aria-hidden />
          <AlertDescription>{t("resources.detail.inactiveNotice")}</AlertDescription>
        </Alert>
      )}
      {data.current_assignment && <CurrentAssignmentNotice resource={data} />}
      {data.is_active &&
        hasPermission(user, "resources:update_status") &&
        (canWriteOrganization(user, data.organization.id) ? (
          <StatusActions resource={data} onReload={reload} />
        ) : (
          // Fuera de su ámbito: lo ve (D4), pero no lo modifica (CLAUDE.md §2.11).
          <p className="flex items-center gap-1.5 text-muted-foreground">
            <Lock aria-hidden className="size-4 shrink-0" />
            {t("resources.detail.outOfScope", { organization: data.organization.name })}
          </p>
        ))}
      <SummaryOrEdit resource={data} canManage={canManage} onReload={reload} />
    </div>
  )
}

/** Asignación activa: el recurso está trabajando en un incidente. */
function CurrentAssignmentNotice({ resource }: { resource: Resource }) {
  const { t } = useTranslation()
  const assignment = resource.current_assignment
  if (!assignment) return null
  return (
    <Alert>
      <Link2 aria-hidden />
      <AlertDescription className="flex flex-col gap-1">
        <p>
          {t("resources.assignment.assignedTo")}{" "}
          <Link
            to={`/incidents/${assignment.incident_id}`}
            className="font-data font-medium underline underline-offset-4"
          >
            {assignment.incident_code}
          </Link>{" "}
          · {t("resources.assignment.since")} <DateTimeText value={assignment.assigned_at} />
          {assignment.arrived_at && <> · {t("resources.assignment.arrived")}</>}
        </p>
        <EtaText eta={assignment.eta} assignedAt={assignment.assigned_at} />
        <p className="text-muted-foreground">{t("resources.assignment.statusLocked")}</p>
      </AlertDescription>
    </Alert>
  )
}

/** Cambio de estado operativo: cualquier estado distinto del actual. Mientras
 * está asignado, su estado lo gobierna la asignación (se retira desde el incidente). */
function StatusActions({ resource, onReload }: { resource: Resource; onReload: () => void }) {
  const { t } = useTranslation()
  const change = useChangeResourceStatus(resource.id)
  const assigned = resource.current_assignment !== null

  return (
    <section aria-label={t("resources.actions.label")} className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {RESOURCE_STATUS_CODES.filter((status) => status !== resource.status).map((status) => {
          const Icon = RESOURCE_STATUS_ICONS[status]
          return (
            <Button
              key={status}
              variant="outline"
              disabled={change.isPending || assigned}
              onClick={() => {
                change.mutate({ status, version: resource.version })
              }}
            >
              <Icon data-icon="inline-start" aria-hidden />
              {t(`resources.actions.toStatus.${status}`)}
            </Button>
          )
        })}
      </div>
      {change.isError && (
        <MutationErrorAlert
          error={change.error}
          message={resourceErrorMessage(change.error, t)}
          conflict={conflictTexts(t)}
          onReload={() => {
            change.reset()
            onReload()
          }}
        />
      )}
    </section>
  )
}

function SummaryOrEdit({
  resource,
  canManage,
  onReload,
}: {
  resource: Resource
  canManage: boolean
  onReload: () => void
}) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const [editing, setEditing] = useState(false)
  const [confirmingDeactivation, setConfirmingDeactivation] = useState(false)
  const update = useUpdateResource(resource.id)
  // Los catálogos del formulario solo se piden a quien puede editar.
  const types = useResourceTypes({ enabled: canManage && editing })
  const organizations = useOrganizations({ enabled: canManage && editing })

  const updateError = update.isError && (
    <MutationErrorAlert
      error={update.error}
      message={resourceErrorMessage(update.error, t)}
      conflict={conflictTexts(t)}
      onReload={() => {
        update.reset()
        onReload()
      }}
    />
  )

  if (editing && canManage) {
    const ready = types.data && organizations.data
    return (
      <Panel
        title={t("resources.detail.editTitle")}
        status={types.isError || organizations.isError ? "error" : ready ? "ready" : "loading"}
        error={{ description: resourceErrorMessage(types.error ?? organizations.error, t) }}
      >
        {ready && (
          <ResourceForm
            // Tras recargar una versión nueva, el formulario se reinicia con sus datos.
            key={resource.version}
            mode="edit"
            types={types.data}
            organizations={organizations.data}
            defaultValues={resourceValuesFrom(resource)}
            pending={update.isPending}
            submitLabel={t("common.save")}
            pendingLabel={t("common.saving")}
            error={updateError}
            onSubmit={(values) => {
              const payload = toUpdatePayload(values, resource)
              // Sin cambios reales no se llama a la API (no habría versión nueva).
              if (!payload) {
                setEditing(false)
                return
              }
              update.mutate(payload, {
                onSuccess: () => {
                  setEditing(false)
                },
              })
            }}
            onCancel={() => {
              update.reset()
              setEditing(false)
            }}
          />
        )}
      </Panel>
    )
  }

  const setActive = (isActive: boolean) => {
    update.mutate(
      { version: resource.version, is_active: isActive },
      {
        onSettled: () => {
          setConfirmingDeactivation(false)
        },
      }
    )
  }

  return (
    <Panel
      title={t("resources.detail.summary")}
      actions={
        canManage && (
          <>
            <Button
              variant="outline"
              size="sm"
              // Un recurso asignado no se desactiva: antes se retira desde el incidente.
              disabled={update.isPending || resource.current_assignment !== null}
              onClick={() => {
                if (resource.is_active) setConfirmingDeactivation(true)
                else setActive(true)
              }}
            >
              <Power data-icon="inline-start" aria-hidden />
              {resource.is_active
                ? t("resources.actions.deactivate")
                : t("resources.actions.reactivate")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                update.reset()
                setEditing(true)
              }}
            >
              <Pencil data-icon="inline-start" aria-hidden />
              {t("common.edit")}
            </Button>
          </>
        )
      }
    >
      <div className="flex flex-col gap-4">
        {updateError}
        <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2 xl:grid-cols-3">
          <DetailItem label={t("resources.fields.type")}>
            {label("resourceTypes", resource.type.code)}
          </DetailItem>
          <DetailItem label={t("resources.fields.category")}>
            {label("resourceCategories", resource.type.category)}
          </DetailItem>
          <DetailItem label={t("resources.fields.organization")}>
            {resource.organization.name}
          </DetailItem>
          <DetailItem label={t("resources.fields.municipality")}>
            {resource.base.municipality}
          </DetailItem>
          <DetailItem label={t("resources.fields.baseDescription")}>
            {resource.base.description ?? "—"}
          </DetailItem>
          <DetailItem label={t("resources.fields.baseCoordinates")}>
            <CoordinatesText location={resource.base} />
          </DetailItem>
          <DetailItem label={t("resources.fields.statusChangedAt")}>
            <DateTimeText value={resource.status_changed_at} />
          </DetailItem>
          <DetailItem label={t("resources.fields.updatedAt")}>
            <DateTimeText value={resource.updated_at} />
          </DetailItem>
        </dl>
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <History aria-hidden className="size-3.5" />
          {t("resources.detail.noStatusHistory")}
        </p>
      </div>

      <ConfirmDialog
        open={confirmingDeactivation}
        onOpenChange={setConfirmingDeactivation}
        pending={update.isPending}
        title={t("resources.actions.confirmDeactivate.title", { code: resource.code })}
        description={t("resources.actions.confirmDeactivate.description")}
        confirmLabel={t("resources.actions.deactivate")}
        cancelLabel={t("resources.actions.confirmDeactivate.keep")}
        onConfirm={() => {
          setActive(false)
        }}
      />
    </Panel>
  )
}
