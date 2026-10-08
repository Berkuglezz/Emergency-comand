import { TriangleAlert } from "lucide-react"
import { Suspense, useCallback, useState } from "react"
import { useTranslation } from "react-i18next"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { inDemoArea, type LngLat } from "@/features/map/config"
import { PointMap } from "@/features/map/lazy"
import { formatCoordinates } from "@/lib/format"

import { roundCoordinate } from "../form"

interface LocationPickerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Posición actual `[longitud, latitud]`, si la hay. */
  initial: LngLat | null
  onConfirm: (latitude: number, longitude: number) => void
}

/**
 * Elegir la posición con un clic en el mapa (o arrastrando el punto). Los
 * campos numéricos del formulario siguen siendo la fuente de verdad: esto solo
 * los rellena, y funciona igual sin mapa base.
 */
export function LocationPickerDialog({
  open,
  onOpenChange,
  initial,
  onConfirm,
}: LocationPickerDialogProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("incidents.location.pickTitle")}</DialogTitle>
          <DialogDescription>{t("incidents.location.pickDescription")}</DialogDescription>
        </DialogHeader>
        {/* Se monta al abrir: cada apertura parte de la posición del formulario. */}
        {open && (
          <Picker
            initial={initial}
            onCancel={() => {
              onOpenChange(false)
            }}
            onConfirm={(latitude, longitude) => {
              onConfirm(latitude, longitude)
              onOpenChange(false)
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Picker({
  initial,
  onCancel,
  onConfirm,
}: {
  initial: LngLat | null
  onCancel: () => void
  onConfirm: (latitude: number, longitude: number) => void
}) {
  const { t } = useTranslation()
  const [point, setPoint] = useState<LngLat | null>(initial)
  const pick = useCallback(([longitude, latitude]: LngLat) => {
    setPoint([roundCoordinate(longitude), roundCoordinate(latitude)])
  }, [])
  const outside = point !== null && !inDemoArea(point[1], point[0])

  return (
    <>
      <Suspense fallback={<Skeleton className="h-80" />}>
        <PointMap
          point={point}
          label={t("incidents.location.pickMapLabel")}
          onPick={pick}
          className="h-80"
        />
      </Suspense>
      <p aria-live="polite">
        {point ? (
          <span className="font-data">{formatCoordinates(point[1], point[0])}</span>
        ) : (
          <span className="text-muted-foreground">{t("incidents.location.pickNone")}</span>
        )}
      </p>
      {outside && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden />
          <AlertDescription>{t("incidents.validation.outOfArea")}</AlertDescription>
        </Alert>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button
          type="button"
          disabled={point === null || outside}
          onClick={() => {
            if (point) onConfirm(point[1], point[0])
          }}
        >
          {t("incidents.location.pickConfirm")}
        </Button>
      </DialogFooter>
    </>
  )
}
