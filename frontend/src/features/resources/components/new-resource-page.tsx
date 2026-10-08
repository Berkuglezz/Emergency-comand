import { TriangleAlert } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useNavigate } from "react-router"

import { Panel, type PanelStatus } from "@/components/ops/panel"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useOrganizations } from "@/features/organizations/hooks"

import { emptyResourceValues, toCreatePayload } from "../form"
import { useCreateResource, useResourceTypes } from "../hooks"
import { resourceErrorMessage } from "../presentation"
import { ResourceForm } from "./resource-form"

/** Alta de un recurso. Visible con `resources:manage`; el backend lo exige. */
export function NewResourcePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const types = useResourceTypes()
  const organizations = useOrganizations()
  const create = useCreateResource()

  let status: PanelStatus = "ready"
  if (types.isPending || organizations.isPending) status = "loading"
  else if (types.isError || organizations.isError) status = "error"

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-3">
      <h1 className="sr-only">{t("resources.create.title")}</h1>
      <Panel
        title={t("resources.create.title")}
        description={t("resources.create.description")}
        status={status}
        error={{
          description: resourceErrorMessage(types.error ?? organizations.error, t),
          onRetry: () => {
            void types.refetch()
            void organizations.refetch()
          },
        }}
      >
        {types.data && organizations.data && (
          <ResourceForm
            mode="create"
            types={types.data}
            organizations={organizations.data}
            defaultValues={emptyResourceValues()}
            pending={create.isPending}
            submitLabel={t("resources.create.submit")}
            pendingLabel={t("resources.create.submitting")}
            error={
              create.isError && (
                <Alert variant="destructive">
                  <TriangleAlert aria-hidden />
                  <AlertDescription>{resourceErrorMessage(create.error, t)}</AlertDescription>
                </Alert>
              )
            }
            onSubmit={(values) => {
              create.mutate(toCreatePayload(values), {
                onSuccess: (resource) => {
                  void navigate(`/resources/${resource.id}`, { replace: true })
                },
              })
            }}
            onCancel={() => {
              void navigate("/resources")
            }}
          />
        )}
      </Panel>
    </div>
  )
}
