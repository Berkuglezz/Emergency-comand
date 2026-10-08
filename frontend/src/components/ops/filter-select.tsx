import { useTranslation } from "react-i18next"

import { Label } from "@/components/ui/label"
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select"

interface FilterSelectProps {
  id: string
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
  /** Añade la opción «Todos» (valor vacío). */
  includeAny?: boolean
  className?: string
}

/** Selector compacto de una barra de filtros (etiqueta encima, opción «Todos»). */
export function FilterSelect({
  id,
  label,
  value,
  options,
  onChange,
  includeAny = true,
  className = "w-44",
}: FilterSelectProps) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      <NativeSelect
        id={id}
        value={value}
        onChange={(event) => {
          onChange(event.target.value)
        }}
        className={className}
      >
        {includeAny && <NativeSelectOption value="">{t("ops.filters.any")}</NativeSelectOption>}
        {options.map((option) => (
          <NativeSelectOption key={option.value} value={option.value}>
            {option.label}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </div>
  )
}
