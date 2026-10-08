import { FlaskConical } from "lucide-react"
import { useTranslation } from "react-i18next"

import { StatusPill } from "./status-pill"

/** Marca de dato simulado: siempre visible junto al dato (CLAUDE.md §8). */
export function SimulatedPill() {
  const { t } = useTranslation()
  return (
    <StatusPill tone="info" icon={FlaskConical}>
      <span title={t("ops.simulatedHint")}>{t("ops.simulated")}</span>
    </StatusPill>
  )
}
