import { Building2 } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Panel, type PanelStatus } from "@/components/ops/panel"
import { StatusPill } from "@/components/ops/status-pill"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ApiError } from "@/lib/api-client"

import { useOrganizations } from "../hooks"

/** Organizaciones (lectura). Visible con `organizations:read`; el backend lo exige. */
export function OrganizationsPage() {
  const { t } = useTranslation()
  const organizations = useOrganizations()

  let status: PanelStatus = "ready"
  if (organizations.isPending) status = "loading"
  else if (organizations.isError) status = "error"
  else if (organizations.data.length === 0) status = "empty"

  const forbidden = organizations.error instanceof ApiError && organizations.error.status === 403

  return (
    <Panel
      title={t("organizations.title")}
      description={t("organizations.description")}
      status={status}
      empty={{ icon: Building2, description: t("organizations.empty") }}
      error={{
        description: forbidden ? t("errors.forbidden.description") : undefined,
        onRetry: forbidden ? undefined : () => void organizations.refetch(),
      }}
      className="h-full"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("organizations.columns.name")}</TableHead>
            <TableHead>{t("organizations.columns.code")}</TableHead>
            <TableHead>{t("organizations.columns.status")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {organizations.data?.map((organization) => (
            <TableRow key={organization.id}>
              <TableCell className="font-medium">{organization.name}</TableCell>
              <TableCell className="font-data text-muted-foreground">{organization.code}</TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <StatusPill tone={organization.is_active ? "ok" : "inactive"}>
                    {organization.is_active
                      ? t("organizations.active")
                      : t("organizations.inactive")}
                  </StatusPill>
                  {organization.is_simulated && (
                    <StatusPill tone="info">{t("organizations.simulated")}</StatusPill>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Panel>
  )
}
