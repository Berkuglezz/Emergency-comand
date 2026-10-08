/**
 * Genera `src/types/api.ts` a partir del OpenAPI del backend de desarrollo.
 *
 *   pnpm gen:api                       # http://localhost:8000/openapi.json
 *   OPENAPI_URL=http://host:8000/openapi.json pnpm gen:api
 *
 * Falla con un mensaje claro (código de salida 1) si el backend no responde o
 * si el esquema no es un OpenAPI 3.x válido. Nunca deja un fichero vacío o a
 * medias: escribe en un temporal y lo renombra solo al final.
 */

import { mkdir, rename, rm, writeFile } from "node:fs/promises"
import { dirname } from "node:path"
import { fileURLToPath } from "node:url"

import openapiTS, { astToString } from "openapi-typescript"

const OPENAPI_URL = process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json"
const OUTPUT = fileURLToPath(new URL("../src/types/api.ts", import.meta.url))
const TIMEOUT_MS = 10_000
// Rutas que siempre deben existir: detectan un esquema truncado o de otra API.
const REQUIRED_PATHS = ["/api/v1/health", "/api/v1/auth/login", "/api/v1/auth/me"]

function fail(message) {
  console.error(`\n✖ gen:api: ${message}\n  No se ha modificado ${OUTPUT}.\n`)
  process.exit(1)
}

async function fetchSchema() {
  let response
  try {
    response = await fetch(OPENAPI_URL, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch (error) {
    const reason = error?.cause?.code ?? error?.name ?? String(error)
    fail(
      `no se pudo conectar con ${OPENAPI_URL} (${reason}).\n` +
        "  Arranca el backend en desarrollo, p. ej. `docker compose up -d db backend`."
    )
  }
  if (!response.ok) {
    fail(
      `${OPENAPI_URL} respondió HTTP ${response.status}.\n` +
        "  El esquema OpenAPI solo se publica con ENVIRONMENT=development."
    )
  }
  try {
    return await response.json()
  } catch {
    fail(`la respuesta de ${OPENAPI_URL} no es JSON válido.`)
  }
}

function validateSchema(schema) {
  const isObject = (value) => typeof value === "object" && value !== null && !Array.isArray(value)

  if (!isObject(schema)) fail("el esquema no es un objeto JSON.")
  if (typeof schema.openapi !== "string" || !/^3\.\d+\.\d+$/.test(schema.openapi)) {
    fail(`versión OpenAPI no soportada: ${JSON.stringify(schema.openapi)} (se espera 3.x).`)
  }
  if (!isObject(schema.info) || typeof schema.info.title !== "string") {
    fail("el esquema no tiene `info.title`.")
  }
  if (!isObject(schema.paths) || Object.keys(schema.paths).length === 0) {
    fail("el esquema no contiene rutas (`paths` vacío).")
  }
  const missing = REQUIRED_PATHS.filter((path) => !(path in schema.paths))
  if (missing.length > 0) fail(`faltan rutas esperadas en el esquema: ${missing.join(", ")}.`)
  if (!isObject(schema.components) || !isObject(schema.components.schemas)) {
    fail("el esquema no contiene `components.schemas`.")
  }
}

async function generate(schema) {
  try {
    return astToString(await openapiTS(schema))
  } catch (error) {
    fail(`openapi-typescript no pudo procesar el esquema: ${error?.message ?? error}`)
  }
}

const schema = await fetchSchema()
validateSchema(schema)
const body = await generate(schema)
if (!body.includes("export interface paths") || !body.includes("export interface components")) {
  fail("la salida generada está incompleta.")
}

const header = [
  "/**",
  " * Tipos de la API de Emergency Command.",
  ` * Generado por \`pnpm gen:api\` desde el OpenAPI ${schema.openapi} de "${schema.info.title}" v${schema.info.version}.`,
  " * NO EDITAR A MANO: regenerar tras cambiar el backend.",
  " */",
  "",
  "",
].join("\n")

const temporary = `${OUTPUT}.tmp`
try {
  await mkdir(dirname(OUTPUT), { recursive: true })
  await writeFile(temporary, header + body, "utf8")
  await rename(temporary, OUTPUT)
} catch (error) {
  await rm(temporary, { force: true })
  fail(`no se pudo escribir el fichero: ${error?.message ?? error}`)
}

console.log(`✔ gen:api: ${Object.keys(schema.paths).length} rutas → src/types/api.ts`)
