import { describe, expect, it } from "vitest"

import i18n from "./config"
import es from "./locales/es.json"

describe("i18n", () => {
  it("carga todos los bloques de es.json (en desarrollo)", () => {
    // `config.ts` importa es.json por bloques: un bloque nuevo que no se añada
    // allí tendría tipos pero no textos en ejecución.
    const loaded = Object.keys(i18n.getResourceBundle("es", "translation") as object)
    expect(loaded.sort()).toEqual(Object.keys(es).sort())
  })

  it("usa español como único idioma", () => {
    expect(i18n.language).toBe("es")
  })
})
