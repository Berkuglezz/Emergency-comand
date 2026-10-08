import { ArrowLeft } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link, useLocation } from "react-router"

import { returnTarget } from "@/lib/navigation"

/** «Volver» a la pantalla de origen con sus filtros; si no la hay, a `fallback`. */
export function BackLink({ fallback }: { fallback: string }) {
  const { t } = useTranslation()
  const location = useLocation()
  return (
    <Link
      to={returnTarget(location.state, fallback)}
      className="inline-flex w-fit items-center gap-1 text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft aria-hidden className="size-4" />
      {t("common.back")}
    </Link>
  )
}
