import { zodResolver } from "@hookform/resolvers/zod"
import { MapPinned, X } from "lucide-react"
import { type ReactNode, useId, useMemo, useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { useTranslation } from "react-i18next"
import type { z } from "zod"

import { FormField } from "@/components/ops/form-field"
import { PRIORITY_CODES } from "@/components/ops/priority"
import { Button } from "@/components/ui/button"
import { useCodeLabel } from "@/lib/code-label"
import { fieldProps } from "@/lib/form-a11y"
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { Textarea } from "@/components/ui/textarea"

import {
  createIncidentFormSchema,
  DETAILS_FIELDS,
  type IncidentFormValues,
  parseCoordinate,
  VEGETATION_CODES,
} from "../form"
import { useIncidents } from "../hooks"
import type { IncidentType } from "../types"
import { LocationPickerDialog } from "./location-picker-dialog"

type Schema = ReturnType<typeof createIncidentFormSchema>

interface IncidentFormProps {
  mode: "create" | "edit"
  types: IncidentType[]
  defaultValues: IncidentFormValues
  /** En edición: el propio incidente no puede ser su padre. */
  incidentId?: string
  /** Un incidente con hijos no puede pasar a ser hijo (un solo nivel). */
  hasChildren?: boolean
  pending: boolean
  submitLabel: string
  pendingLabel: string
  /** Error de la API, ya traducido, que se muestra sobre los botones. */
  error?: ReactNode
  onSubmit: (values: IncidentFormValues, type: IncidentType | undefined) => void
  onCancel: () => void
}

export function IncidentForm({
  mode,
  types,
  defaultValues,
  incidentId,
  hasChildren = false,
  pending,
  submitLabel,
  pendingLabel,
  error,
  onSubmit,
  onCancel,
}: IncidentFormProps) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const id = useId()
  const schema = useMemo(() => createIncidentFormSchema(t), [t])
  const form = useForm<z.input<Schema>, unknown, z.output<Schema>>({
    resolver: zodResolver(schema),
    defaultValues,
  })
  const { errors } = form.formState

  const [picking, setPicking] = useState(false)
  const [latitudeText, longitudeText] = useWatch({
    control: form.control,
    name: ["latitude", "longitude"],
  })
  const currentLatitude = parseCoordinate(latitudeText)
  const currentLongitude = parseCoordinate(longitudeText)
  const setCoordinates = (latitude: string, longitude: string) => {
    const options = { shouldDirty: true, shouldValidate: form.formState.isSubmitted }
    form.setValue("latitude", latitude, options)
    form.setValue("longitude", longitude, options)
  }

  const typeId = useWatch({ control: form.control, name: "type_id" })
  const selectedType = types.find((type) => type.id === typeId)
  const schemaKey = selectedType?.details_schema_key
  const detailFields: readonly string[] =
    schemaKey && schemaKey in DETAILS_FIELDS
      ? DETAILS_FIELDS[schemaKey as keyof typeof DETAILS_FIELDS]
      : []

  // Candidatos a padre: incidentes activos que no son hijos de otro (un nivel).
  const parents = useIncidents({ active: true, sort: "-reported_at", limit: 100 })
  const parentOptions = (parents.data?.items ?? []).filter(
    (incident) => incident.parent_incident_id === null && incident.id !== incidentId
  )

  const submit = form.handleSubmit((values) => {
    onSubmit(values, selectedType)
  })

  return (
    <form noValidate onSubmit={(event) => void submit(event)} aria-busy={pending}>
      <FieldGroup className="gap-4">
        {mode === "create" ? (
          <FormField id={`${id}-type`} label={t("incidents.fields.type")} error={errors.type_id}>
            <NativeSelect
              {...fieldProps(`${id}-type`, errors.type_id)}
              {...form.register("type_id")}
            >
              <NativeSelectOption value="">{t("incidents.fields.selectType")}</NativeSelectOption>
              {types
                .filter((type) => type.is_active)
                .map((type) => (
                  <NativeSelectOption key={type.id} value={type.id}>
                    {label("incidentTypes", type.code)}
                  </NativeSelectOption>
                ))}
            </NativeSelect>
          </FormField>
        ) : (
          <Field>
            <FieldLabel>{t("incidents.fields.type")}</FieldLabel>
            <p>{selectedType ? label("incidentTypes", selectedType.code) : "—"}</p>
          </Field>
        )}

        <FormField id={`${id}-title`} label={t("incidents.fields.title")} error={errors.title}>
          <Input
            maxLength={200}
            {...fieldProps(`${id}-title`, errors.title)}
            {...form.register("title")}
          />
        </FormField>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id={`${id}-priority`}
            label={t("incidents.fields.priority")}
            error={errors.priority}
          >
            <NativeSelect
              {...fieldProps(`${id}-priority`, errors.priority)}
              {...form.register("priority")}
            >
              {mode === "create" && (
                <NativeSelectOption value="">
                  {selectedType
                    ? t("incidents.fields.priorityDefaultWith", {
                        priority: t(`priority.${selectedType.default_priority}`),
                      })
                    : t("incidents.fields.priorityDefaultWith", { priority: "—" })}
                </NativeSelectOption>
              )}
              {PRIORITY_CODES.map((code) => (
                <NativeSelectOption key={code} value={code}>
                  {t(`priority.${code}`)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FormField>
          <FormField
            id={`${id}-affected`}
            label={t("incidents.fields.affectedPeople")}
            error={errors.affected_people}
          >
            <Input
              inputMode="numeric"
              {...fieldProps(`${id}-affected`, errors.affected_people)}
              {...form.register("affected_people")}
            />
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id={`${id}-municipality`}
            label={t("incidents.fields.municipality")}
            error={errors.municipality}
          >
            <Input
              maxLength={100}
              {...fieldProps(`${id}-municipality`, errors.municipality)}
              {...form.register("municipality")}
            />
          </FormField>
          <FormField
            id={`${id}-location`}
            label={t("incidents.fields.locationDescription")}
            description={t("incidents.fields.locationHint")}
            error={errors.location_description}
          >
            <Input
              maxLength={255}
              {...fieldProps(`${id}-location`, errors.location_description)}
              {...form.register("location_description")}
            />
          </FormField>
        </div>

        <FieldSet className="gap-3 rounded-lg border p-3">
          <FieldLegend variant="label">{t("incidents.fields.coordinates")}</FieldLegend>
          <p className="text-xs text-muted-foreground">{t("incidents.location.coordinatesHint")}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              id={`${id}-latitude`}
              label={t("incidents.fields.latitude")}
              error={errors.latitude}
            >
              <Input
                inputMode="decimal"
                placeholder={t("incidents.location.latitudePlaceholder")}
                className="font-data"
                {...fieldProps(`${id}-latitude`, errors.latitude)}
                {...form.register("latitude")}
              />
            </FormField>
            <FormField
              id={`${id}-longitude`}
              label={t("incidents.fields.longitude")}
              error={errors.longitude}
            >
              <Input
                inputMode="decimal"
                placeholder={t("incidents.location.longitudePlaceholder")}
                className="font-data"
                {...fieldProps(`${id}-longitude`, errors.longitude)}
                {...form.register("longitude")}
              />
            </FormField>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setPicking(true)
              }}
            >
              <MapPinned data-icon="inline-start" aria-hidden />
              {t("incidents.location.pick")}
            </Button>
            {(latitudeText.trim() !== "" || longitudeText.trim() !== "") && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setCoordinates("", "")
                }}
              >
                <X data-icon="inline-start" aria-hidden />
                {t("incidents.location.clear")}
              </Button>
            )}
          </div>
          <LocationPickerDialog
            open={picking}
            onOpenChange={setPicking}
            initial={
              currentLatitude !== null && currentLongitude !== null
                ? [currentLongitude, currentLatitude]
                : null
            }
            onConfirm={(latitude, longitude) => {
              setCoordinates(String(latitude), String(longitude))
            }}
          />
        </FieldSet>

        <FormField
          id={`${id}-description`}
          label={t("incidents.fields.description")}
          error={errors.description}
        >
          <Textarea
            rows={3}
            maxLength={5000}
            {...fieldProps(`${id}-description`, errors.description)}
            {...form.register("description")}
          />
        </FormField>

        {detailFields.length > 0 && (
          <FieldSet className="gap-3 rounded-lg border p-3">
            <FieldLegend variant="label">{t("incidents.fields.details")}</FieldLegend>
            <div className="grid gap-4 sm:grid-cols-2">
              {detailFields.includes("affected_hectares") && (
                <FormField
                  id={`${id}-hectares`}
                  label={t("incidentDetails.affected_hectares")}
                  error={errors.details?.affected_hectares}
                >
                  <Input
                    inputMode="decimal"
                    {...fieldProps(`${id}-hectares`, errors.details?.affected_hectares)}
                    {...form.register("details.affected_hectares")}
                  />
                </FormField>
              )}
              {detailFields.includes("vegetation") && (
                <FormField
                  id={`${id}-vegetation`}
                  label={t("incidentDetails.vegetation")}
                  error={errors.details?.vegetation}
                >
                  <NativeSelect
                    {...fieldProps(`${id}-vegetation`, errors.details?.vegetation)}
                    {...form.register("details.vegetation")}
                  >
                    <NativeSelectOption value="">—</NativeSelectOption>
                    {VEGETATION_CODES.map((code) => (
                      <NativeSelectOption key={code} value={code}>
                        {t(`incidentDetails.vegetationValues.${code}`)}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </FormField>
              )}
              {detailFields.includes("water_level_cm") && (
                <FormField
                  id={`${id}-water`}
                  label={t("incidentDetails.water_level_cm")}
                  error={errors.details?.water_level_cm}
                >
                  <Input
                    inputMode="numeric"
                    {...fieldProps(`${id}-water`, errors.details?.water_level_cm)}
                    {...form.register("details.water_level_cm")}
                  />
                </FormField>
              )}
            </div>
          </FieldSet>
        )}

        <FormField
          id={`${id}-parent`}
          label={t("incidents.fields.parent")}
          description={t("incidents.fields.parentHint")}
          error={errors.parent_incident_id}
        >
          <NativeSelect
            disabled={hasChildren}
            {...fieldProps(`${id}-parent`, errors.parent_incident_id)}
            {...form.register("parent_incident_id")}
          >
            <NativeSelectOption value="">{t("incidents.fields.noParent")}</NativeSelectOption>
            {parentOptions.map((incident) => (
              <NativeSelectOption key={incident.id} value={incident.id}>
                {incident.code} · {incident.title}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </FormField>

        {error}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" disabled={pending} onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? pendingLabel : submitLabel}
          </Button>
        </div>
      </FieldGroup>
    </form>
  )
}
