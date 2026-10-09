import { useCallback, useState } from "react"

const PREFIX = "ec.layout."

function read(key: string): boolean | null {
  try {
    const value = window.localStorage.getItem(PREFIX + key)
    return value === null ? null : value === "1"
  } catch {
    return null
  }
}

function write(key: string, value: boolean): void {
  try {
    window.localStorage.setItem(PREFIX + key, value ? "1" : "0")
  } catch {
    // Sin almacenamiento (modo privado, bloqueado…): la preferencia dura la sesión.
  }
}

/**
 * Preferencia de disposición de este navegador (panel plegado o desplegado).
 * Es solo comodidad: no es estado de la aplicación ni viaja en la URL, y si el
 * almacenamiento falla se usa el valor por defecto.
 */
export function usePersistedToggle(key: string, defaultValue: boolean | (() => boolean)) {
  const [value, setValue] = useState<boolean>(() => {
    const stored = read(key)
    if (stored !== null) return stored
    return typeof defaultValue === "function" ? defaultValue() : defaultValue
  })

  const set = useCallback(
    (next: boolean) => {
      setValue(next)
      write(key, next)
    },
    [key]
  )

  return [value, set] as const
}

/** ¿La ventana alcanza este ancho? Sin `matchMedia` (tests), se supone que sí. */
export function viewportAtLeast(width: number): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia(`(min-width: ${String(width)}px)`).matches
    : true
}
