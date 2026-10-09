import { TriangleAlert } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { Panel, type PanelStatus } from "@/components/ops/panel"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { hasPermission, useSession } from "@/features/auth/hooks"

import { emptyFormValues, toCreatePayload } from "../form"
import { useCreateIncident, useIncidentTypes } from "../hooks"
import { incidentErrorMessage } from "../presentation"
import { IncidentForm } from "./incident-form"

/** Alta de un incidente. Visible con `incidents:create`; el backend lo exige. */
export function NewIncidentPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const types = useIncidentTypes()
  const create = useCreateIncident()
  const { data: user } = useSession()
  // Elegir la prioridad inicial o el incidente padre exige la edición completa
  // (CLAUDE.md §2.11, D10 y D11).
  const canSetPriority = hasPermission(user, "incidents:update")

  let status: PanelStatus = "ready"
  if (types.isPending) status = "loading"
  else if (types.isError) status = "error"

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
      <h1 className="sr-only">{t("incidents.create.title")}</h1>
      <Panel
        title={t("incidents.create.title")}
        description={t("incidents.create.description")}
        status={status}
        error={{
          description: incidentErrorMessage(types.error, t),
          onRetry: () => void types.refetch(),
        }}
      >
        {types.data && (
          <IncidentForm
            mode="create"
            types={types.data}
            defaultValues={emptyFormValues()}
            canSetPriority={canSetPriority}
            canSetParent={canSetPriority}
            pending={create.isPending}
            submitLabel={t("incidents.create.submit")}
            pendingLabel={t("incidents.create.submitting")}
            error={
              create.isError && (
                <Alert variant="destructive">
                  <TriangleAlert aria-hidden />
                  <AlertDescription>{incidentErrorMessage(create.error, t)}</AlertDescription>
                </Alert>
              )
            }
            onSubmit={(values, type) => {
              const payload = toCreatePayload(values, type?.details_schema_key)
              create.mutate(
                canSetPriority ? payload : { ...payload, priority: null, parent_incident_id: null },
                {
                  onSuccess: (incident) => {
                    void navigate(`/incidents/${incident.id}`, { replace: true })
                  },
                }
              )
            }}
            onCancel={() => {
              void navigate("/incidents")
            }}
          />
        )}
      </Panel>
    </div>
  )
}
