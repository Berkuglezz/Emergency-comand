import { MapPinOff } from "lucide-react"
import { useTranslation } from "react-i18next"

/** Indicador «sin coordenadas» junto al municipio: icono con nombre accesible y tooltip. */
export function UnlocatedMark() {
  const { t } = useTranslation()
  return (
    <MapPinOff
      role="img"
      aria-label={t("incidents.location.noCoordinates")}
      className="size-3.5 shrink-0 text-muted-foreground"
    >
      <title>{t("incidents.location.noCoordinates")}</title>
    </MapPinOff>
  )
}
