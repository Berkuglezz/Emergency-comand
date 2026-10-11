import { useMemo } from "react"
import { useTranslation } from "react-i18next"

export type CodeGroup =
  | "incidentTypes"
  | "incidentCategories"
  | "incidentRisks"
  | "incidentFields"
  | "locationFields"
  | "mapFeatureKinds"
  | "mapFeatureFields"
  | "resourceTypes"
  | "resourceCategories"

/**
 * Etiquetas de códigos de catálogo. Los catálogos viven en la base de datos:
 * si llega un código sin traducción, se muestra el propio código en lugar de
 * romper la pantalla.
 */
export function useCodeLabel(): (group: CodeGroup, code: string) => string {
  const { t } = useTranslation()
  return useMemo(() => {
    const dictionaries: Record<CodeGroup, Record<string, string>> = {
      incidentTypes: t("incidentTypes", { returnObjects: true }),
      incidentCategories: t("incidentCategories", { returnObjects: true }),
      incidentRisks: t("incidentRisks", { returnObjects: true }),
      incidentFields: t("incidentFields", { returnObjects: true }),
      locationFields: t("locationFields", { returnObjects: true }),
      mapFeatureKinds: t("mapFeatureKinds", { returnObjects: true }),
      mapFeatureFields: t("mapFeatureFields", { returnObjects: true }),
      resourceTypes: t("resourceTypes", { returnObjects: true }),
      resourceCategories: t("resourceCategories", { returnObjects: true }),
    }
    return (group, code) => dictionaries[group][code] ?? code
  }, [t])
}
