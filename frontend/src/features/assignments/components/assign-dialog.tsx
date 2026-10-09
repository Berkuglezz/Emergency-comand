import { Lightbulb, Plus, Repeat } from "lucide-react"
import { useId, useState } from "react"
import { useTranslation } from "react-i18next"

import { ConfirmDialog } from "@/components/ops/confirm-dialog"
import { EtaText } from "@/components/ops/eta-text"
import { FilterSelect } from "@/components/ops/filter-select"
import { MutationErrorAlert } from "@/components/ops/mutation-error-alert"
import { Panel, type PanelStatus } from "@/components/ops/panel"
import { StatusPill } from "@/components/ops/status-pill"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { IncidentDetail } from "@/features/incidents/types"
import { ResourceTypeLabel } from "@/features/resources/components/resource-badges"
import { useResourceTypes } from "@/features/resources/hooks"
import { useCodeLabel } from "@/lib/code-label"

import { useAssignmentCandidates, useAssignResource } from "../hooks"
import { assignmentErrorMessage } from "../presentation"
import type { AssignmentCandidate } from "../types"

interface AssignDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  incident: IncidentDetail
}

/**
 * Asignar un recurso. El sistema informa (candidatos ordenados por ETA
 * estimada, tipos sugeridos marcados), la persona elige y confirma. Nunca se
 * preselecciona ni se asigna nada automáticamente.
 */
export function AssignDialog({ open, onOpenChange, incident }: AssignDialogProps) {
  const { t } = useTranslation()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{t("assignments.dialog.title", { code: incident.code })}</DialogTitle>
          <DialogDescription>{t("assignments.dialog.description")}</DialogDescription>
        </DialogHeader>
        {/* Se monta al abrir: cada apertura parte de los datos actuales. */}
        {open && (
          <Candidates
            incident={incident}
            onDone={() => {
              onOpenChange(false)
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Candidates({ incident, onDone }: { incident: IncidentDetail; onDone: () => void }) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const id = useId()
  const [type, setType] = useState("")
  const [includeAssigned, setIncludeAssigned] = useState(false)
  const [reassigning, setReassigning] = useState<AssignmentCandidate | null>(null)
  const types = useResourceTypes()
  const candidates = useAssignmentCandidates(incident.id, {
    type: type || undefined,
    include_assigned: includeAssigned || undefined,
  })
  const assign = useAssignResource(incident.id)

  const submit = (candidate: AssignmentCandidate) => {
    assign.mutate(
      {
        resource_id: candidate.resource.id,
        version: incident.version,
        reassign: candidate.current_incident !== null,
      },
      {
        onSuccess: onDone,
        onSettled: () => {
          setReassigning(null)
        },
      }
    )
  }

  let status: PanelStatus = "ready"
  if (candidates.isPending) status = "loading"
  else if (candidates.isError) status = "error"
  else if (candidates.data.length === 0) status = "empty"

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <FilterSelect
          id={`${id}-type`}
          label={t("assignments.dialog.type")}
          value={type}
          onChange={setType}
          options={(types.data ?? []).map((resourceType) => ({
            value: resourceType.code,
            label: label("resourceTypes", resourceType.code),
          }))}
        />
        <label className="flex h-8 items-center gap-2 px-1">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={includeAssigned}
            onChange={(event) => {
              setIncludeAssigned(event.target.checked)
            }}
          />
          {t("assignments.dialog.includeAssigned")}
        </label>
      </div>

      {assign.isError && (
        <MutationErrorAlert
          error={assign.error}
          message={assignmentErrorMessage(assign.error, t)}
          conflict={{
            title: t("incidents.detail.conflict.title"),
            description: t("incidents.detail.conflict.description"),
          }}
          onReload={() => {
            assign.reset()
            onDone()
          }}
        />
      )}

      <Panel
        title={t("assignments.dialog.candidates")}
        description={t("assignments.dialog.sortedByEta")}
        status={status}
        empty={{ description: t("assignments.dialog.empty") }}
        error={{
          description: assignmentErrorMessage(candidates.error, t),
          onRetry: () => void candidates.refetch(),
        }}
        className="max-h-[60vh]"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("assignments.dialog.columns.resource")}</TableHead>
              <TableHead>{t("assignments.dialog.columns.type")}</TableHead>
              <TableHead>{t("assignments.dialog.columns.organization")}</TableHead>
              <TableHead>{t("assignments.dialog.columns.eta")}</TableHead>
              <TableHead>
                <span className="sr-only">{t("assignments.dialog.columns.action")}</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {candidates.data?.map((candidate) => {
              const { resource } = candidate
              return (
                <TableRow key={resource.id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-data font-medium">{resource.code}</span>
                      <span className="text-xs text-muted-foreground">{resource.name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <ResourceTypeLabel type={resource.type} />
                      {candidate.suggested && (
                        <StatusPill tone="info" icon={Lightbulb}>
                          {t("assignments.dialog.suggested")}
                        </StatusPill>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-48 truncate">{resource.organization.name}</TableCell>
                  <TableCell>
                    <EtaText eta={candidate.eta} unavailable={candidate.eta_unavailable} />
                  </TableCell>
                  <TableCell className="text-right">
                    {candidate.current_incident ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={assign.isPending}
                        aria-label={t("assignments.dialog.reassignFor", {
                          code: resource.code,
                          incident: candidate.current_incident.code,
                        })}
                        onClick={() => {
                          setReassigning(candidate)
                        }}
                      >
                        <Repeat data-icon="inline-start" aria-hidden />
                        {t("assignments.dialog.reassign", {
                          incident: candidate.current_incident.code,
                        })}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        disabled={assign.isPending}
                        aria-label={t("assignments.dialog.assignFor", { code: resource.code })}
                        onClick={() => {
                          submit(candidate)
                        }}
                      >
                        <Plus data-icon="inline-start" aria-hidden />
                        {t("assignments.dialog.assign")}
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Panel>

      <ConfirmDialog
        open={reassigning !== null}
        onOpenChange={(next) => {
          if (!next) setReassigning(null)
        }}
        pending={assign.isPending}
        title={t("assignments.confirmReassign.title", {
          code: reassigning?.resource.code ?? "",
          from: reassigning?.current_incident?.code ?? "",
          to: incident.code,
        })}
        description={t("assignments.confirmReassign.description", {
          from: reassigning?.current_incident?.code ?? "",
        })}
        confirmLabel={t("assignments.confirmReassign.confirm")}
        onConfirm={() => {
          if (reassigning) submit(reassigning)
        }}
      />
    </div>
  )
}
