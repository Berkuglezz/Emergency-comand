import { useTranslation } from "react-i18next"

/** Error inesperado al renderizar una ruta. No muestra detalles técnicos. */
export function RouteError() {
  const { t } = useTranslation()

  return (
    <main
      role="alert"
      className="flex min-h-dvh flex-col items-center justify-center gap-2 p-6 text-center"
    >
      <h1 className="text-xl font-semibold">{t("errors.unexpected.title")}</h1>
      <p className="text-muted-foreground">{t("errors.unexpected.description")}</p>
    </main>
  )
}
