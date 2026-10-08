import { describe, expect, it } from "vitest"

import { PAGE_SIZE, parseFilters, serializeFilters, toListParams } from "./filters"

describe("filtros del listado", () => {
  it("sin parámetros: activos por prioridad, primera página", () => {
    const filters = parseFilters(new URLSearchParams())
    expect(toListParams(filters)).toEqual({
      q: undefined,
      status: undefined,
      priority: undefined,
      type: undefined,
      active: true,
      sort: "priority",
      limit: PAGE_SIZE,
      offset: 0,
    })
    expect(serializeFilters(filters).toString()).toBe("")
  })

  it("ignora valores desconocidos en la URL en lugar de enviarlos a la API", () => {
    const filters = parseFilters(
      new URLSearchParams("status=borrado&priority=urgentisima&sort=nombre&page=-2")
    )
    expect(filters).toMatchObject({ status: null, priority: null, sort: "priority", page: 1 })
  })

  it("ida y vuelta URL → filtros → URL", () => {
    const search =
      "q=incendio&status=closed&priority=high&type=wildfire&closed=1&sort=-reported_at&page=3"
    expect(serializeFilters(parseFilters(new URLSearchParams(search))).toString()).toBe(search)
  })

  it("incluir cerrados o elegir un estado busca también entre los finalizados", () => {
    expect(toListParams(parseFilters(new URLSearchParams("closed=1"))).active).toBe(false)
    expect(toListParams(parseFilters(new URLSearchParams("status=cancelled"))).active).toBe(false)
  })

  it("la página se traduce a offset", () => {
    expect(toListParams(parseFilters(new URLSearchParams("page=3"))).offset).toBe(2 * PAGE_SIZE)
  })
})
