import { useTranslation } from "react-i18next"

/** Mientras se carga el código de la primera ruta (páginas bajo demanda). */
export function RouteLoading() {
  const { t } = useTranslation()
  return (
    <div role="status" className="flex min-h-dvh items-center justify-center text-muted-foreground">
      {t("common.loading")}
    </div>
  )
}
