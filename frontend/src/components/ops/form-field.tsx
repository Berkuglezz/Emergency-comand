import type { ReactNode } from "react"
import type { FieldError as FormFieldError } from "react-hook-form"

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"

/** Campo de formulario: etiqueta, control, ayuda opcional y error accesible. */
export function FormField({
  id,
  label,
  description,
  error,
  children,
}: {
  id: string
  label: string
  description?: string
  error: FormFieldError | undefined
  children: ReactNode
}) {
  return (
    <Field data-invalid={error ? true : undefined}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children}
      {description && <FieldDescription>{description}</FieldDescription>}
      {error?.message && <FieldError id={`${id}-error`}>{error.message}</FieldError>}
    </Field>
  )
}
