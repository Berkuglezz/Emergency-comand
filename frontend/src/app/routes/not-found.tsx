import { useTranslation } from "react-i18next"
import { Link } from "react-router"

export function NotFound() {
  const { t } = useTranslation()

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-2 p-6 text-center">
      <h1 className="text-xl font-semibold">{t("errors.notFound.title")}</h1>
      <p className="text-muted-foreground">{t("errors.notFound.description")}</p>
      <Link to="/" className="underline underline-offset-4">
        {t("errors.notFound.backHome")}
      </Link>
    </main>
  )
}
