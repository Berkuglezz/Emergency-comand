import type { FieldError } from "react-hook-form"

/** Atributos de accesibilidad de un control con posible error (ver `FormField`). */
export function fieldProps(id: string, error: FieldError | undefined) {
  return {
    id,
    "aria-invalid": error ? true : undefined,
    "aria-describedby": error ? `${id}-error` : undefined,
  } as const
}
