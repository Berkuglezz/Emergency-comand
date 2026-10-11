import i18n from "i18next"
import { initReactI18next } from "react-i18next"

// Importación por claves raíz: Vite elimina del bundle las que no se usan.
// `designSystem` solo se carga en desarrollo, igual que la ruta /dev/design-system.
import {
  app,
  assignments,
  auth,
  commandCenter,
  common,
  coordinates,
  designSystem,
  errors,
  incidentCategories,
  incidentDetails,
  incidentFields,
  incidentRisks,
  incidents,
  incidentStatus,
  incidentTypes,
  layout,
  locationFields,
  map,
  mapFeatureFields,
  mapFeatureKinds,
  mapFeatures,
  nav,
  ops,
  organizations,
  priority,
  resourceCategories,
  resources,
  resourceStatus,
  resourceTypes,
  roles,
  topBar,
} from "./locales/es.json"
import type es from "./locales/es.json"

export const defaultNS = "translation"

/** Forma completa de las traducciones (fuente de los tipos de `t()`). */
export type Translations = typeof es

const translation = {
  common,
  app,
  auth,
  roles,
  nav,
  layout,
  topBar,
  commandCenter,
  map,
  coordinates,
  assignments,
  organizations,
  incidents,
  incidentStatus,
  incidentTypes,
  incidentCategories,
  incidentRisks,
  incidentFields,
  locationFields,
  mapFeatureKinds,
  mapFeatureFields,
  mapFeatures,
  incidentDetails,
  resourceTypes,
  resources,
  resourceStatus,
  resourceCategories,
  priority,
  ops,
  errors,
  ...(import.meta.env.DEV ? { designSystem } : {}),
}

// Solo español (CLAUDE.md §3); la estructura admite más idiomas sin cambios.
void i18n.use(initReactI18next).init({
  resources: { es: { [defaultNS]: translation } },
  lng: "es",
  fallbackLng: "es",
  defaultNS,
  interpolation: {
    // React ya escapa el contenido.
    escapeValue: false,
  },
})

export default i18n
