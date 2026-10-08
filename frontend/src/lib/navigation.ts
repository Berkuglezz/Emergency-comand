/**
 * Estado de navegación que guardan los enlaces de un listado: la URL completa
 * (con filtros y página) a la que debe volver «Volver» desde el detalle.
 */
export interface ReturnState {
  from: string
}

export function returnState(location: { pathname: string; search: string }): ReturnState {
  return { from: `${location.pathname}${location.search}` }
}

/** Destino de «Volver»: la ruta guardada si es interna; si no, `fallback`. */
export function returnTarget(state: unknown, fallback: string): string {
  if (typeof state === "object" && state !== null && "from" in state) {
    const { from } = state
    // Solo rutas internas: nunca se vuelve a otra URL.
    if (typeof from === "string" && from.startsWith("/") && !from.startsWith("//")) return from
  }
  return fallback
}
