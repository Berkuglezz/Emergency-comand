/**
 * Query string para la API: omite los valores vacíos y repite el parámetro en
 * las listas (`status=a&status=b`), como espera FastAPI.
 */
export function toQueryString(params: object): string {
  const search = new URLSearchParams()
  // `unknown`: en ejecución los opcionales sin valor llegan como `undefined`.
  for (const [key, value] of Object.entries(params) as [string, unknown][]) {
    if (value === undefined || value === null) continue
    for (const item of Array.isArray(value) ? (value as unknown[]) : [value]) {
      search.append(key, String(item))
    }
  }
  const query = search.toString()
  return query ? `?${query}` : ""
}

/** Valor de la URL solo si es uno de los códigos conocidos; si no, `null`. */
export function oneOf<T extends string>(values: readonly T[], value: string | null): T | null {
  return value !== null && (values as readonly string[]).includes(value) ? (value as T) : null
}

/** Página 1-based leída de la URL (1 si falta o no es válida). */
export function pageFrom(value: string | null): number {
  const page = Number(value)
  return Number.isInteger(page) && page > 1 ? page : 1
}
