import { ShieldX } from "lucide-react"
import { useTranslation } from "react-i18next"
import { Link } from "react-router"

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"

export function Forbidden() {
  const { t } = useTranslation()
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <ShieldX aria-hidden />
        </EmptyMedia>
        <EmptyTitle>
          <h1>{t("errors.forbidden.title")}</h1>
        </EmptyTitle>
        <EmptyDescription>{t("errors.forbidden.description")}</EmptyDescription>
        <Link to="/" className="underline underline-offset-4">
          {t("errors.notFound.backHome")}
        </Link>
      </EmptyHeader>
    </Empty>
  )
}
