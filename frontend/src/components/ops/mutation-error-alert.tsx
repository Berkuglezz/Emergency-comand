import { RotateCw, TriangleAlert } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { isVersionConflict } from "@/lib/api-client"

interface MutationErrorAlertProps {
  error: unknown
  /** Mensaje ya traducido para errores que no son un conflicto de versión. */
  message: string
  /** Textos del conflicto 409 `version_conflict`, específicos de cada entidad. */
  conflict: { title: string; description: string }
  onReload: () => void
}

/**
 * Error de una escritura. Un 409 `version_conflict` (otra persona cambió el
 * registro) ofrece recargar en lugar de reintentar a ciegas: nunca se
 * sobrescribe un cambio ajeno («gana el último» no existe).
 */
export function MutationErrorAlert({
  error,
  message,
  conflict,
  onReload,
}: MutationErrorAlertProps) {
  const { t } = useTranslation()

  if (isVersionConflict(error)) {
    return (
      <Alert variant="destructive">
        <TriangleAlert aria-hidden />
        <AlertTitle>{conflict.title}</AlertTitle>
        <AlertDescription>
          <p>{conflict.description}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={onReload}>
            <RotateCw data-icon="inline-start" aria-hidden />
            {t("ops.conflict.reload")}
          </Button>
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <Alert variant="destructive">
      <TriangleAlert aria-hidden />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}
