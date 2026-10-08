/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Estilo del mapa base (MapLibre). Opcional: por defecto, OpenFreeMap `dark`. */
  readonly VITE_MAP_STYLE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
