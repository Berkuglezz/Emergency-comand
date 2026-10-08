import type { ReactNode } from "react"

import { formatDateTime } from "@/lib/format"

/** Par etiqueta/valor de una ficha (dentro de un `<dl>`). */
export function DetailItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  )
}

/** Fecha y hora de la API mostrada en Europe/Madrid, con cifras tabulares. */
export function DateTimeText({ value }: { value: string }) {
  return (
    <time dateTime={value} className="font-data">
      {formatDateTime(value)}
    </time>
  )
}
