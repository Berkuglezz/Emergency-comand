/**
 * Ámbito organizativo en la interfaz (CLAUDE.md §2.11, R.7). La interfaz solo
 * ayuda: el backend falso aplica las mismas reglas que el real y responde 403
 * `organization_out_of_scope` si se intenta igualmente.
 */
import { screen, within } from "@testing-library/react"
import { beforeEach, describe, expect, it } from "vitest"

import {
  type FakeBackend,
  installFakeBackend,
  ORGANIZATION,
  OTHER_ORGANIZATION,
} from "./fake-backend"
import { renderApp } from "./render-app"

let backend: FakeBackend

beforeEach(() => {
  backend = installFakeBackend()
})

const OUT_OF_SCOPE_NOTICE = /puedes consultarlo, pero solo su organización o la coordinación/

function seedResources() {
  const own = backend.resources.add({ code: "SIM-PROPIO" })
  const other = backend.resources.add({ code: "SIM-AJENO", organization: OTHER_ORGANIZATION })
  return { own, other }
}

describe("estado operativo de los recursos", () => {
  it("el operador cambia el estado de los suyos, no el de otra organización", async () => {
    const { own, other } = seedResources()
    backend.startSessionFor("operator")
    const { router } = renderApp(`/resources/${own.id}`)

    expect(await screen.findByRole("button", { name: "Poner en servicio" })).toBeInTheDocument()

    await router.navigate(`/resources/${other.id}`)
    // Lo ve (D4), pero sin acciones de estado y con el motivo.
    expect(await screen.findByRole("heading", { name: /SIM-AJENO/ })).toBeInTheDocument()
    expect(screen.getByText(OUT_OF_SCOPE_NOTICE)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Poner en servicio" })).not.toBeInTheDocument()
  })

  it("el operador sin organización no cambia el estado de ningún recurso", async () => {
    const { own } = seedResources()
    backend.startSessionFor("operator", { organization: null })
    renderApp(`/resources/${own.id}`)

    expect(await screen.findByText(OUT_OF_SCOPE_NOTICE)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Poner en servicio" })).not.toBeInTheDocument()
  })

  it.each(["coordinator", "admin"] as const)(
    "%s cambia el estado de recursos de cualquier organización",
    async (role) => {
      const { other } = seedResources()
      backend.startSessionFor(role)
      const { user } = renderApp(`/resources/${other.id}`)

      await user.click(await screen.findByRole("button", { name: "Poner en servicio" }))
      expect(await screen.findByRole("button", { name: "Marcar disponible" })).toBeInTheDocument()
      expect(screen.queryByText(OUT_OF_SCOPE_NOTICE)).not.toBeInTheDocument()
    }
  )

  it("si la API rechaza por ámbito, se explica sin detalles internos", async () => {
    const { own } = seedResources()
    backend.startSessionFor("operator")
    const { user } = renderApp(`/resources/${own.id}`)
    const button = await screen.findByRole("button", { name: "Poner en servicio" })

    // Entretanto, el recurso pasa a otra organización: la interfaz va desfasada.
    backend.resources.byCode("SIM-PROPIO").organization = OTHER_ORGANIZATION
    await user.click(button)

    expect(
      await screen.findByText(
        "Este recurso pertenece a otra organización: tu rol solo puede modificar los recursos de la tuya. No se ha guardado nada."
      )
    ).toBeInTheDocument()
    expect(backend.resources.byCode("SIM-PROPIO").status).toBe("available")
  })
})

describe("«En el lugar» y retirada", () => {
  function seedAssigned() {
    seedResources()
    const incident = backend.incidents.add({ title: "Con dos organizaciones" })
    backend.assignments.assign(incident.code, "SIM-PROPIO")
    backend.assignments.assign(incident.code, "SIM-AJENO")
    return incident
  }

  async function panel(): Promise<HTMLElement> {
    const heading = await screen.findByRole("heading", { name: "Recursos asignados" })
    const section = heading.closest("section")
    if (!section) throw new Error("panel")
    await within(section).findByRole("link", { name: "SIM-AJENO" })
    return section
  }

  it("el operador solo marca la llegada de los recursos de su organización", async () => {
    const incident = seedAssigned()
    backend.startSessionFor("operator")
    renderApp(`/incidents/${incident.id}`)
    const section = await panel()

    expect(
      within(section).getByRole("button", { name: "Marcar SIM-PROPIO en el lugar" })
    ).toBeInTheDocument()
    expect(
      within(section).queryByRole("button", { name: "Marcar SIM-AJENO en el lugar" })
    ).not.toBeInTheDocument()
    // Sigue sin poder asignar ni retirar (permisos, no ámbito).
    expect(within(section).queryByRole("button", { name: /^Retirar/ })).not.toBeInTheDocument()
  })

  it("el operador sin organización no marca ninguna llegada", async () => {
    const incident = seedAssigned()
    backend.startSessionFor("operator", { organization: null })
    renderApp(`/incidents/${incident.id}`)
    const section = await panel()

    expect(within(section).queryByRole("button", { name: /en el lugar$/ })).not.toBeInTheDocument()
  })

  it.each(["coordinator", "admin"] as const)(
    "%s marca la llegada y retira recursos de cualquier organización",
    async (role) => {
      const incident = seedAssigned()
      backend.startSessionFor(role)
      renderApp(`/incidents/${incident.id}`)
      const section = await panel()

      for (const code of ["SIM-PROPIO", "SIM-AJENO"]) {
        expect(
          within(section).getByRole("button", { name: `Marcar ${code} en el lugar` })
        ).toBeInTheDocument()
        expect(within(section).getByRole("button", { name: `Retirar ${code}` })).toBeInTheDocument()
      }
    }
  )
})

describe("alta de incidente", () => {
  it.each([
    ["operator", false],
    ["coordinator", true],
    ["admin", true],
  ] as const)("%s: selector de incidente padre visible = %s", async (role, visible) => {
    backend.startSessionFor(role)
    renderApp("/incidents/new")

    await screen.findByLabelText("Tipo de incidente")
    if (visible) expect(screen.getByLabelText("Incidente padre")).toBeInTheDocument()
    else expect(screen.queryByLabelText("Incidente padre")).not.toBeInTheDocument()
  })
})

describe("sesión", () => {
  it("el ámbito llega del backend con la sesión", async () => {
    backend.startSessionFor("operator")
    renderApp("/")
    await screen.findByRole("heading", { name: "Mapa" })

    const me = backend.users.find((candidate) => candidate.role === "operator")
    expect(me?.scope.write).toEqual({
      all_organizations: false,
      organization_ids: [ORGANIZATION.id],
    })
  })
})
