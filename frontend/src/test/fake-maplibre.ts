/**
 * Doble de `maplibre-gl` para los tests (jsdom no tiene WebGL). Se registra en
 * `setup.ts` con `vi.mock`.
 *
 * - `Map` guarda las llamadas de cámara (`easeTo`, `fitBounds`) y emite `load`
 *   (o `error`, o lanza al crearse, según `FakeMap.mode`).
 * - `Marker` añade su elemento dentro del contenedor del mapa: los marcadores
 *   son botones reales que los tests pueden buscar y pulsar.
 */

type LngLatTuple = [number, number]
interface MapEvent {
  lngLat?: { lng: number; lat: number }
}
type Handler = (event: MapEvent) => void

export type FakeMapMode = "ok" | "basemap_error" | "unsupported"

export class Map {
  static mode: FakeMapMode = "ok"
  static instances: Map[] = []

  readonly container: HTMLElement
  readonly calls: { method: string; args: unknown[] }[] = []
  /** Zona visible: Asturias por defecto. */
  visible: [LngLatTuple, LngLatTuple] = [
    [-7.2, 42.85],
    [-4.5, 43.7],
  ]
  removed = false
  readonly touchZoomRotate = { disableRotation: () => undefined }
  private readonly handlers = new globalThis.Map<string, Set<Handler>>()
  private readonly canvas = document.createElement("canvas")

  constructor(options: { container: HTMLElement }) {
    if (Map.mode === "unsupported") throw new Error("WebGL2 no disponible")
    this.container = options.container
    Map.instances.push(this)
    queueMicrotask(() => {
      this.fire(Map.mode === "basemap_error" ? "error" : "load")
    })
  }

  static reset(): void {
    Map.mode = "ok"
    Map.instances = []
  }

  on(type: string, handler: Handler): this {
    const set = this.handlers.get(type) ?? new Set<Handler>()
    set.add(handler)
    this.handlers.set(type, set)
    return this
  }

  off(type: string, handler: Handler): this {
    this.handlers.get(type)?.delete(handler)
    return this
  }

  /** Emite un evento como lo haría MapLibre (p. ej. `click` con `lngLat`). */
  fire(type: string, event: MapEvent = {}): void {
    for (const handler of this.handlers.get(type) ?? []) handler(event)
  }

  addControl(): this {
    return this
  }

  remove(): void {
    this.removed = true
  }

  getCanvas(): HTMLCanvasElement {
    return this.canvas
  }

  getBounds(): { contains: (point: LngLatTuple) => boolean } {
    const [[west, south], [east, north]] = this.visible
    return {
      contains: ([lng, lat]) => lng >= west && lng <= east && lat >= south && lat <= north,
    }
  }

  easeTo(...args: unknown[]): this {
    this.calls.push({ method: "easeTo", args })
    return this
  }

  fitBounds(...args: unknown[]): this {
    this.calls.push({ method: "fitBounds", args })
    return this
  }
}

export class Marker {
  readonly element: HTMLElement
  private position: LngLatTuple = [0, 0]
  private readonly handlers = new globalThis.Map<string, () => void>()

  constructor(options: { element: HTMLElement }) {
    this.element = options.element
  }

  setLngLat(position: LngLatTuple): this {
    this.position = position
    this.element.dataset.lngLat = position.join(",")
    return this
  }

  getLngLat(): { lng: number; lat: number } {
    return { lng: this.position[0], lat: this.position[1] }
  }

  addTo(map: Map): this {
    map.container.appendChild(this.element)
    return this
  }

  remove(): this {
    this.element.remove()
    return this
  }

  on(type: string, handler: () => void): this {
    this.handlers.set(type, handler)
    return this
  }

  addClassName(name: string): void {
    this.element.classList.add(name)
  }

  removeClassName(name: string): void {
    this.element.classList.remove(name)
  }
}

export class NavigationControl {
  readonly options: unknown

  constructor(options: unknown = {}) {
    this.options = options
  }
}

export function setWorkerUrl(): void {
  // Sin worker en los tests.
}
