// Formato de presentación en español. Las fechas se almacenan en UTC y se
// muestran en Europe/Madrid (CLAUDE.md §3).
export const DISPLAY_TIME_ZONE = "Europe/Madrid"

const numberFormat = new Intl.NumberFormat("es-ES")

const timeFormat = new Intl.DateTimeFormat("es-ES", {
  timeZone: DISPLAY_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
})

const dateFormat = new Intl.DateTimeFormat("es-ES", {
  timeZone: DISPLAY_TIME_ZONE,
  weekday: "short",
  day: "2-digit",
  month: "short",
})

const dateTimeFormat = new Intl.DateTimeFormat("es-ES", {
  timeZone: DISPLAY_TIME_ZONE,
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
})

export function formatNumber(value: number): string {
  return numberFormat.format(value)
}

/** Hora en Europe/Madrid, formato 24 h con segundos (p. ej. 14:07:31). */
export function formatTime(date: Date): string {
  return timeFormat.format(date)
}

/** Fecha corta en Europe/Madrid (p. ej. «mié, 07 oct»). */
export function formatShortDate(date: Date): string {
  return dateFormat.format(date)
}

/** Fecha y hora en Europe/Madrid (p. ej. «07 oct, 14:07»). Acepta ISO 8601 de la API. */
export function formatDateTime(value: Date | string): string {
  return dateTimeFormat.format(typeof value === "string" ? new Date(value) : value)
}
