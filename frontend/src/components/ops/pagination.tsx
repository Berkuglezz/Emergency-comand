import { ChevronLeft, ChevronRight } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"

interface PaginationProps {
  page: number
  pages: number
  onChange: (page: number) => void
}

/** Paginación anterior/siguiente con la página actual (1-based). */
export function Pagination({ page, pages, onChange }: PaginationProps) {
  const { t } = useTranslation()
  return (
    <nav
      aria-label={t("ops.pagination.label")}
      className="mt-3 flex items-center justify-end gap-2"
    >
      <span className="font-data text-xs text-muted-foreground">
        {page} / {pages}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={page <= 1}
        onClick={() => {
          onChange(page - 1)
        }}
      >
        <ChevronLeft data-icon="inline-start" aria-hidden />
        {t("ops.pagination.previous")}
      </Button>
      <Button
        variant="outline"
        size="sm"
        disabled={page >= pages}
        onClick={() => {
          onChange(page + 1)
        }}
      >
        {t("ops.pagination.next")}
        <ChevronRight data-icon="inline-end" aria-hidden />
      </Button>
    </nav>
  )
}
