import { zodResolver } from "@hookform/resolvers/zod"
import { type ReactNode, useId, useMemo } from "react"
import { useForm, useWatch } from "react-hook-form"
import { useTranslation } from "react-i18next"
import type { z } from "zod"

import { FormField } from "@/components/ops/form-field"
import { Button } from "@/components/ui/button"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"
import { CoordinatesFieldset } from "@/features/map/coordinates-fieldset"
import type { Organization } from "@/features/organizations/hooks"
import { useCodeLabel } from "@/lib/code-label"
import { fieldProps } from "@/lib/form-a11y"

import { createResourceFormSchema, type ResourceFormValues } from "../form"
import { RESOURCE_STATUS_CODES } from "../presentation"
import type { ResourceType } from "../types"

type Schema = ReturnType<typeof createResourceFormSchema>

interface ResourceFormProps {
  mode: "create" | "edit"
  types: ResourceType[]
  organizations: Organization[]
  defaultValues: ResourceFormValues
  pending: boolean
  submitLabel: string
  pendingLabel: string
  error?: ReactNode
  onSubmit: (values: ResourceFormValues) => void
  onCancel: () => void
}

/** Ficha del recurso (alta y edición). Solo con `resources:manage`. */
export function ResourceForm({
  mode,
  types,
  organizations,
  defaultValues,
  pending,
  submitLabel,
  pendingLabel,
  error,
  onSubmit,
  onCancel,
}: ResourceFormProps) {
  const { t } = useTranslation()
  const label = useCodeLabel()
  const id = useId()
  const schema = useMemo(() => createResourceFormSchema(t), [t])
  const form = useForm<z.input<Schema>, unknown, z.output<Schema>>({
    resolver: zodResolver(schema),
    defaultValues,
  })
  const { errors } = form.formState
  const [latitudeText, longitudeText] = useWatch({
    control: form.control,
    name: ["latitude", "longitude"],
  })
  const setCoordinates = (latitude: string, longitude: string) => {
    const options = { shouldDirty: true, shouldValidate: form.formState.isSubmitted }
    form.setValue("latitude", latitude, options)
    form.setValue("longitude", longitude, options)
  }

  // Solo se ofrecen tipos y organizaciones activos, más los actuales del recurso
  // (puede seguir en uno que se desactivó después).
  const typeOptions = types.filter((type) => type.is_active || type.id === defaultValues.type_id)
  const organizationOptions = organizations.filter(
    (organization) => organization.is_active || organization.id === defaultValues.organization_id
  )

  const submit = form.handleSubmit((values) => {
    onSubmit(values)
  })

  return (
    <form noValidate onSubmit={(event) => void submit(event)} aria-busy={pending}>
      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {mode === "create" ? (
            <FormField
              id={`${id}-code`}
              label={t("resources.fields.code")}
              description={t("resources.fields.codeHint")}
              error={errors.code}
            >
              <Input
                maxLength={32}
                autoCapitalize="characters"
                className="font-data uppercase"
                {...fieldProps(`${id}-code`, errors.code)}
                {...form.register("code")}
              />
            </FormField>
          ) : (
            <Field>
              <FieldLabel>{t("resources.fields.code")}</FieldLabel>
              <p className="font-data">{defaultValues.code}</p>
            </Field>
          )}
          <FormField id={`${id}-name`} label={t("resources.fields.name")} error={errors.name}>
            <Input
              maxLength={200}
              {...fieldProps(`${id}-name`, errors.name)}
              {...form.register("name")}
            />
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id={`${id}-type`} label={t("resources.fields.type")} error={errors.type_id}>
            <NativeSelect
              {...fieldProps(`${id}-type`, errors.type_id)}
              {...form.register("type_id")}
            >
              <NativeSelectOption value="">{t("resources.fields.selectType")}</NativeSelectOption>
              {typeOptions.map((type) => (
                <NativeSelectOption key={type.id} value={type.id}>
                  {label("resourceTypes", type.code)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FormField>
          <FormField
            id={`${id}-organization`}
            label={t("resources.fields.organization")}
            error={errors.organization_id}
          >
            <NativeSelect
              {...fieldProps(`${id}-organization`, errors.organization_id)}
              {...form.register("organization_id")}
            >
              <NativeSelectOption value="">
                {t("resources.fields.selectOrganization")}
              </NativeSelectOption>
              {organizationOptions.map((organization) => (
                <NativeSelectOption key={organization.id} value={organization.id}>
                  {organization.name}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id={`${id}-municipality`}
            label={t("resources.fields.municipality")}
            error={errors.municipality}
          >
            <Input
              maxLength={100}
              {...fieldProps(`${id}-municipality`, errors.municipality)}
              {...form.register("municipality")}
            />
          </FormField>
          <FormField
            id={`${id}-base`}
            label={t("resources.fields.baseDescription")}
            error={errors.base_description}
          >
            <Input
              maxLength={255}
              {...fieldProps(`${id}-base`, errors.base_description)}
              {...form.register("base_description")}
            />
          </FormField>
        </div>

        <CoordinatesFieldset
          id={id}
          legend={t("resources.fields.baseCoordinates")}
          latitude={{
            register: form.register("latitude"),
            error: errors.latitude,
            value: latitudeText,
          }}
          longitude={{
            register: form.register("longitude"),
            error: errors.longitude,
            value: longitudeText,
          }}
          onChange={setCoordinates}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          {mode === "create" && (
            <FormField
              id={`${id}-status`}
              label={t("resources.fields.initialStatus")}
              error={errors.status}
            >
              <NativeSelect
                {...fieldProps(`${id}-status`, errors.status)}
                {...form.register("status")}
              >
                <NativeSelectOption value="">
                  {t("resources.fields.statusDefault")}
                </NativeSelectOption>
                {RESOURCE_STATUS_CODES.filter((code) => code !== "available").map((code) => (
                  <NativeSelectOption key={code} value={code}>
                    {t(`resourceStatus.${code}`)}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </FormField>
          )}
        </div>

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
