import type { defaultNS, Translations } from "./config"

// Claves de traducción tipadas: `t("clave.inexistente")` es un error de compilación.
declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS
    resources: { translation: Translations }
  }
}
