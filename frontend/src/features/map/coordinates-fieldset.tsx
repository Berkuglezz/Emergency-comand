import { MapPinned, X } from "lucide-react"
import { useState } from "react"
import type { FieldError, UseFormRegisterReturn } from "react-hook-form"
import { useTranslation } from "react-i18next"

import { FormField } from "@/components/ops/form-field"
import { Button } from "@/components/ui/button"
import { FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { parseCoordinate } from "@/lib/coordinates"
import { fieldProps } from "@/lib/form-a11y"

import { LocationPickerDialog } from "./location-picker-dialog"

interface CoordinatesFieldsetProps {
  id: string
  legend: string
  latitude: { register: UseFormRegisterReturn; error?: FieldError; value: string }
  longitude: { register: UseFormRegisterReturn; error?: FieldError; value: string }
  /** Fija ambos valores (elegir en el mapa o quitarlos). */
  onChange: (latitude: string, longitude: string) => void
}

/**
 * Latitud y longitud de un formulario, con «Elegir en el mapa» y «Quitar
 * coordenadas». Los campos son la fuente de verdad: el mapa solo los rellena.
 */
export function CoordinatesFieldset({
  id,
  legend,
  latitude,
  longitude,
  onChange,
}: CoordinatesFieldsetProps) {
  const { t } = useTranslation()
  const [picking, setPicking] = useState(false)
  const currentLatitude = parseCoordinate(latitude.value)
  const currentLongitude = parseCoordinate(longitude.value)

  return (
    <FieldSet className="gap-3 rounded-lg border p-3">
      <FieldLegend variant="label">{legend}</FieldLegend>
      <p className="text-xs text-muted-foreground">{t("coordinates.hint")}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField id={`${id}-latitude`} label={t("coordinates.latitude")} error={latitude.error}>
          <Input
            inputMode="decimal"
            placeholder={t("coordinates.latitudePlaceholder")}
            className="font-data"
            {...fieldProps(`${id}-latitude`, latitude.error)}
            {...latitude.register}
          />
        </FormField>
        <FormField
          id={`${id}-longitude`}
          label={t("coordinates.longitude")}
          error={longitude.error}
        >
          <Input
            inputMode="decimal"
            placeholder={t("coordinates.longitudePlaceholder")}
            className="font-data"
            {...fieldProps(`${id}-longitude`, longitude.error)}
            {...longitude.register}
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
          {t("coordinates.pick")}
        </Button>
        {(latitude.value.trim() !== "" || longitude.value.trim() !== "") && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              onChange("", "")
            }}
          >
            <X data-icon="inline-start" aria-hidden />
            {t("coordinates.clear")}
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
        onConfirm={(lat, lon) => {
          onChange(String(lat), String(lon))
        }}
      />
    </FieldSet>
  )
}
