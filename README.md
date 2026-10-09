# Emergency Command

Prototipo demostrable de una plataforma de coordinación de emergencias: un centro de mando para gestionar incidentes y recursos, con autenticación, permisos por rol y un sistema de diseño propio pensado para operaciones.

> **⚠️ Prototipo de demostración.** Emergency Command **no es un sistema real de emergencias** y **no está conectado** al 112, a servicios públicos ni a ninguna fuente real de datos. Todas las organizaciones, usuarios, recursos e incidentes que incluye son **ficticios y están marcados como simulados**.

**Estado actual: Fase 4.** Funciona:

- autenticación y control de acceso por rol (RBAC);
- **incidentes:** alta, edición, ciclo de vida con cambios de estado validados, incidente padre, historial (timeline) y notas;
- **recursos:** alta, edición, estado operativo y desactivación;
- **centro de mando** con datos reales: indicadores, **mapa** de incidentes activos, incidentes activos, incidente seleccionado y resumen de recursos;
- **ubicaciones con PostGIS:** coordenadas validadas en cada incidente, minimapa en la ficha y selección de la posición en el mapa al dar de alta o editar;
- **asignación de recursos:** candidatos ordenados por **ETA estimada** (el sistema informa; la persona decide y confirma), «en el lugar», retirada con motivo, reasignación y retirada automática al cerrar; bases de los recursos asignados en el mapa;
- datos simulados de Asturias para la demo.

Todavía **no** hay posiciones GPS de recursos, rutas por carretera, tiempo real (WebSockets), simulador, IA ni hospitales: llegan en fases posteriores. La ETA es siempre una **estimación** local (distancia × sinuosidad / velocidad media del tipo), sin servicios externos. La lista completa de lo implementado y lo pendiente está en [`docs/architecture.md`](docs/architecture.md#15-implementado-y-pendiente).

---

## Índice

1. [Requisitos previos](#requisitos-previos)
2. [Puesta en marcha con Docker (recomendado)](#puesta-en-marcha-con-docker-recomendado)
3. [Acceso a la aplicación y usuarios demo](#acceso-a-la-aplicación-y-usuarios-demo)
4. [Recarga en caliente en Docker](#recarga-en-caliente-en-docker)
5. [Ejecución sin Docker](#ejecución-sin-docker)
6. [Base de datos: migraciones y datos demo](#base-de-datos-migraciones-y-datos-demo)
7. [Comandos útiles](#comandos-útiles)
8. [Variables de entorno](#variables-de-entorno)
9. [Estructura del repositorio](#estructura-del-repositorio)
10. [Solución de problemas](#solución-de-problemas)

---

## Requisitos previos

**Con Docker** (la forma recomendada) solo necesitas:

| Herramienta | Versión probada | Notas |
|---|---|---|
| Docker Desktop (con Docker Compose v2) | Docker 29.8, Compose 5.5 | En Windows, con el backend WSL2 |
| Git | cualquiera reciente | |

**Sin Docker** (desarrollo local de backend y frontend) necesitas además:

| Herramienta | Versión | Notas |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 0.12.23 | Gestiona Python y las dependencias del backend |
| Python | 3.13 | Fijado en `backend/.python-version`; uv lo descarga si no lo tienes |
| Node.js | 24 o superior | |
| pnpm | 12.9.1 | Fijado en `frontend/package.json` (`packageManager`) |
| PostgreSQL + PostGIS | PostgreSQL 18, PostGIS 3.6 | Lo más sencillo es usar solo el servicio `db` de Docker Compose |

Imágenes Docker que se usan: `postgis/postgis:18-3.6`, `python:3.13-slim` (con uv 0.12.23) y `node:24-slim` (con pnpm 12.9.1).

---

## Puesta en marcha con Docker (recomendado)

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio> emergency-command
cd emergency-command

# 2. Crear el fichero de entorno a partir del ejemplo
cp .env.example .env
#    (opcional pero recomendado) edita .env y cambia los valores "change-me-…".
#    Para una prueba local, los valores de ejemplo funcionan tal cual.

# 3. Construir y arrancar los tres servicios: db, backend y frontend
docker compose up --build
```

Al arrancar, el contenedor del backend:

1. espera a que la base de datos esté lista;
2. aplica las migraciones (`alembic upgrade head`);
3. **solo con `ENVIRONMENT=development`**, carga los datos demo (`python -m seeds.seed`), sin duplicar nada aunque arranque varias veces;
4. arranca la API en el puerto 8000.

El frontend arranca cuando el backend está sano (healthcheck en `/api/v1/health`).

### Parar y limpiar

```bash
docker compose stop          # parar los contenedores (se conservan los datos)
docker compose down          # parar y eliminar los contenedores (se conservan los datos)
docker compose down -v       # ⚠️ además borra el volumen de la base de datos (datos perdidos)
```

Para arrancar en segundo plano: `docker compose up -d --build`. Para ver los logs: `docker compose logs -f backend` (o `frontend`, `db`).

> Las imágenes son **de desarrollo**: incluyen dependencias de desarrollo y recarga en caliente, y no están pensadas para producción.

---

## Acceso a la aplicación y usuarios demo

| Servicio | URL |
|---|---|
| Aplicación (frontend) | <http://localhost:5173> |
| API | <http://localhost:8000/api/v1> |
| Documentación OpenAPI (solo en `development`) | <http://localhost:8000/docs> |
| PostgreSQL (desde el host) | `localhost:5433` (usuario y base de datos de `.env`) |

Los puertos publicados se configuran en `.env` (`FRONTEND_HOST_PORT`, `BACKEND_HOST_PORT`, `DB_HOST_PORT`). La base de datos se publica en el **5433** para no chocar con un PostgreSQL local en el 5432.

### Usuarios demo

El seed crea un usuario por rol. Solo existen si el seed se ha ejecutado con `ENVIRONMENT=development`.

| Rol | Email | Organización (simulada) |
|---|---|---|
| `admin` | `admin@demo.emergency-command.test` | Centro de Coordinación Demo Asturias |
| `coordinator` | `coordinador@demo.emergency-command.test` | Centro de Coordinación Demo Asturias |
| `operator` | `operador@demo.emergency-command.test` | Parque de Bomberos Demo Oviedo |

**Contraseña:** la de la variable **`DEMO_USER_PASSWORD`** de tu fichero `.env`. No se incluye en este README ni en el código. Si la cambias en `.env`, la siguiente ejecución del seed (o el siguiente arranque del backend en Docker) actualiza la de los tres usuarios.

Qué puede hacer cada rol en esta fase:

| Acción | `admin` | `coordinator` | `operator` |
|---|:-:|:-:|:-:|
| Ver el centro de mando, incidentes y recursos | ✅ | ✅ | ✅ |
| Dar de alta y editar incidentes, cambiar su estado y añadir notas | ✅ | ✅ | ❌ |
| Cerrar y cancelar incidentes | ✅ | ✅ | ❌ |
| Cambiar el estado operativo de un recurso | ✅ | ✅ | ✅ |
| Dar de alta, editar y desactivar recursos | ✅ | ❌ | ❌ |
| Asignar, retirar y reasignar recursos a un incidente | ✅ | ✅ | ❌ |
| Marcar que un recurso asignado está «en el lugar» | ✅ | ✅ | ✅ |
| Ver organizaciones | ✅ | ✅ | ❌ |

Lo que un rol no puede hacer no aparece en la interfaz, y la API responde 403 si se intenta igualmente.

### Datos simulados

Todos los datos demo viven en `backend/seeds/`, son ficticios y la interfaz los marca como «Simulado»:

- **4 organizaciones** de Asturias, con código `sim-…` y «(simulado)» en el nombre;
- **3 usuarios**, uno por rol, con emails del dominio reservado `.test`, que no puede existir en internet;
- **18 recursos** con código `SIM-…` (bomberos, sanitarios, protección civil y apoyo logístico), cada uno con una base simulada con coordenadas aproximadas;
- **asignaciones de ejemplo** coherentes con los estados: los 5 recursos en servicio están asignados a incidentes activos, con su ETA estimada, una llegada, una retirada por «misión cumplida» y una retirada automática al cerrar un incidente;
- **12 incidentes** en Oviedo, Gijón, Avilés y municipios cercanos, con todas las prioridades y estados, incluidos un temporal con dos incidentes agrupados, dos cerrados y uno cancelado, cada uno con su historial;
- ubicaciones genéricas a nivel de municipio («Zona forestal (ubicación simulada)»): ningún teléfono, dirección, URL ni nombre corresponde a un servicio real;
- coordenadas aproximadas (3 decimales, ≈100 m) en zonas genéricas de cada municipio, nunca sobre instalaciones de emergencias. Dos incidentes activos **no tienen coordenadas a propósito** (un temporal que afecta a una zona amplia y un aviso recién recibido), para mostrar ese caso.

Las horas de los incidentes son relativas al momento en que se cargó el seed.

### Mapa

El mapa usa **MapLibre GL JS** con el estilo `dark` de **[OpenFreeMap](https://openfreemap.org)**, gratuito y sin clave:

- **Necesita conexión a internet** para la cartografía. Sin ella, el mapa avisa y sigue mostrando las posiciones de los incidentes.
- **Privacidad:** al proveedor solo se le piden el estilo y las teselas; las coordenadas y los datos de los incidentes nunca salen de la aplicación.
- **Atribución** (© OpenMapTiles, datos © colaboradores de OpenStreetMap): siempre visible en la esquina del mapa.
- Para usar otro estilo, define `VITE_MAP_STYLE_URL` (ver [Variables de entorno](#variables-de-entorno)).
- Las coordenadas de los incidentes deben estar en **Asturias** (área de la demo): una posición fuera, o con latitud y longitud intercambiadas, se rechaza.

---

## Recarga en caliente en Docker

`docker compose up` **no monta** el código fuente en los contenedores: copia el código al construir la imagen. Por tanto:

| Cómo arrancas | ¿Se ven los cambios de código? |
|---|---|
| `docker compose up --build` | **No.** Hay que reconstruir (`docker compose up --build`) para verlos. |
| `docker compose up --build --watch` | **Sí.** Compose sincroniza `backend/` y `frontend/` en los contenedores; uvicorn (`--reload`) y Vite recargan solos. Si cambian `pyproject.toml`/`uv.lock` o `package.json`/`pnpm-lock.yaml`, Compose reconstruye la imagen. |

Se usa `watch` en lugar de montar carpetas porque en Windows los cambios en carpetas montadas no siempre se detectan, y montar `node_modules` o el entorno de Python suele quedarse con dependencias antiguas.

Para un ciclo de desarrollo más rápido también puedes ejecutar backend y frontend fuera de Docker (siguiente sección).

---

## Ejecución sin Docker

La base de datos sigue siendo PostgreSQL con PostGIS; lo más sencillo es levantar solo ese servicio con Docker. Con `.env` copiado de `.env.example`, `POSTGRES_HOST=localhost` y `POSTGRES_PORT=5433` ya apuntan a él.

```bash
# Base de datos (solo el servicio db)
docker compose up -d db
```

### Backend

```bash
cd backend
uv sync                                   # instala Python 3.13 y las dependencias
uv run alembic upgrade head               # migraciones
uv run python -m seeds.seed               # datos demo (solo con ENVIRONMENT=development)
uv run uvicorn app.main:app --reload      # API en http://localhost:8000
```

El backend lee `.env` de la raíz del repositorio.

### Frontend

```bash
cd frontend
pnpm install
pnpm dev                                  # http://localhost:5173
```

Vite redirige `/api` al backend (`http://localhost:8000` por defecto; se cambia con la variable `API_PROXY_TARGET`). El navegador solo habla con el frontend, de modo que la cookie del refresh token es del mismo origen.

---

## Base de datos: migraciones y datos demo

| Tarea | Con Docker | Sin Docker (desde `backend/`) |
|---|---|---|
| Aplicar migraciones | automático al arrancar el backend, o `docker compose exec backend alembic upgrade head` | `uv run alembic upgrade head` |
| Ver la revisión actual | `docker compose exec backend alembic current` | `uv run alembic current` |
| Comprobar que modelos y migraciones coinciden | `docker compose exec backend alembic check` | `uv run alembic check` |
| Cargar datos demo | automático al arrancar en `development`, o `docker compose exec backend python -m seeds.seed` | `uv run python -m seeds.seed` |

- **Migraciones:**
  - la inicial habilita la extensión PostGIS y crea `roles`, `organizations`, `users` y `refresh_tokens`;
  - la de la Fase 2 crea los catálogos de tipos de incidente y de recurso, `incidents`, `incident_events` (historial de solo inserción) y `resources`;
  - las de la Fase 3 crean `locations` (`geometry(Point, 4326)` con índice GiST), trasladan a ella la ubicación de cada incidente y añaden el evento `location_changed`;
  - las de la Fase 4 añaden la velocidad media por tipo de recurso, la base de cada recurso (en `locations`) y `resource_assignments`.
- Los roles y los catálogos de tipos se crean en las migraciones, no en el seed, porque el sistema los necesita en cualquier entorno.
- El seed es idempotente y fuera de `development` se niega a ejecutarse:
  - **usuarios y organizaciones:** crea lo que falta y restaura los datos demo modificados;
  - **recursos e incidentes:** solo crea lo que falta y **nunca modifica lo existente**, así que los cambios que hagas durante una demo se conservan aunque se vuelva a ejecutar.
- **Volver a los datos de demostración iniciales:** `docker compose down -v` borra la base de datos (⚠️ también cualquier dato que hayas creado); el siguiente `docker compose up` la recrea, migra y carga el seed desde cero.
- **Base de datos creada antes de la Fase 4:** las bases de los recursos se quedan sin coordenadas y no hay asignaciones de ejemplo, porque el seed no modifica lo existente. Reinicia la base de datos con `docker compose down -v` para tener los datos demo completos.
- **Base de datos creada antes de la Fase 3:** las migraciones añaden la tabla de ubicaciones, pero los incidentes que ya existían se quedan **sin coordenadas**, porque el seed no modifica lo existente. Para tener los datos demo con coordenadas, reinicia la base de datos con `docker compose down -v` y vuelve a arrancar con `docker compose up --build`.

---

## Comandos útiles

### Backend (desde `backend/`)

```bash
uv run pytest                 # tests (necesita el servicio db levantado)
uv run ruff check .           # lint
uv run ruff format --check .  # formato
uv run mypy                   # tipos (modo estricto)
```

Los tests **no tocan la base de datos de desarrollo**: usan `<POSTGRES_DB>_test`, que se borra, se recrea y se migra desde cero en cada ejecución, y cada test corre dentro de una transacción que se deshace al terminar. Solo necesitan que el servidor PostgreSQL de `db` esté accesible.

Dentro del contenedor: `docker compose exec backend pytest`.

### Frontend (desde `frontend/`)

```bash
pnpm test             # tests (Vitest, sin backend: usan un backend falso en memoria)
pnpm lint             # ESLint en modo estricto con comprobación de tipos
pnpm typecheck        # TypeScript
pnpm build            # build de producción en dist/
pnpm format:check     # Prettier
pnpm gen:api          # regenera src/types/api.ts desde el OpenAPI del backend
```

### Cliente OpenAPI (`pnpm gen:api`)

Los tipos del frontend se generan desde el OpenAPI del backend y no se escriben a mano. Tras cambiar la API:

```bash
# con el backend arrancado en development (Docker o local)
cd frontend
pnpm gen:api
```

- Lee `http://localhost:8000/openapi.json` (se puede cambiar con `OPENAPI_URL`).
- Falla con un mensaje claro y **sin modificar** `src/types/api.ts` si el backend no responde, si no está en `development` (no publica el OpenAPI), o si el esquema no es válido o está incompleto.
- `src/types/api.ts` se versiona en git.

### Catálogo del sistema de diseño

Con el frontend en modo desarrollo, <http://localhost:5173/dev/design-system> muestra los tokens y todos los componentes base en sus estados. Esta ruta **no existe en el build de producción** ni aparece en la navegación.

---

## Variables de entorno

Todas están documentadas en [`.env.example`](.env.example). Resumen:

| Variable | Para qué sirve |
|---|---|
| `ENVIRONMENT` | `development`, `test` o `production`. Solo en `development` existen `/docs`, `/openapi.json` y el seed demo. |
| `LOG_LEVEL` | Nivel de log del backend. Los logs nunca incluyen contraseñas, tokens ni cookies. |
| `DB_HOST_PORT`, `BACKEND_HOST_PORT`, `FRONTEND_HOST_PORT` | Puertos publicados por Docker Compose. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales y nombre de la base de datos. |
| `POSTGRES_HOST`, `POSTGRES_PORT` | Dónde encuentra el backend la base de datos sin Docker (Compose los sobrescribe a `db:5432`). |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM` | Firma de los access tokens. Genera una clave propia: `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Duración de los tokens. |
| `REFRESH_COOKIE_SECURE` | Atributo `Secure` de la cookie de refresh. `false` solo en desarrollo sobre http. |
| `CORS_ORIGINS` | Lista JSON de orígenes permitidos. Nunca `*`. |
| `DEMO_USER_PASSWORD` | Contraseña de los usuarios demo (mínimo 12 caracteres). |
| `VITE_MAP_STYLE_URL` | Estilo del mapa base (frontend). Vacío = OpenFreeMap `dark`. Sin Docker, defínela en el entorno o en `frontend/.env.local`. |

`.env` está en `.gitignore`: **nunca lo subas al repositorio**. Con `ENVIRONMENT=production`, el backend se niega a arrancar si `JWT_SECRET_KEY` o `POSTGRES_PASSWORD` conservan los valores de ejemplo, o si `REFRESH_COOKIE_SECURE` es `false`.

---

## Estructura del repositorio

```
emergency-command/
├─ docker-compose.yml   .env.example   README.md   CLAUDE.md
├─ docs/
│  └─ architecture.md    arquitectura y decisiones
├─ backend/              FastAPI + SQLAlchemy async + Alembic (uv)
│  ├─ app/               api/v1 · services · repositories · models · schemas · domain · core · db
│  ├─ alembic/           migraciones (Fases 1, 2 y 3)
│  ├─ seeds/             datos de demostración (solo development)
│  └─ tests/             unit/ · integration/
└─ frontend/             React + Vite + TypeScript (pnpm)
   ├─ scripts/gen-api.mjs
   └─ src/               app · components/{ui,ops} · features/{auth,command-center,incidents,
                         map,resources,organizations,system} · lib · i18n · styles · types
```

Detalle en [`docs/architecture.md`](docs/architecture.md).

---

## Solución de problemas

- **El puerto 5433/8000/5173 está ocupado.** Cambia `DB_HOST_PORT`, `BACKEND_HOST_PORT` o `FRONTEND_HOST_PORT` en `.env`. El navegador habla con la API a través del proxy de Vite (mismo origen), así que no hace falta tocar `CORS_ORIGINS`; solo importa si un cliente llama a la API directamente desde otro origen.
- **El backend no arranca en Docker.** Revisa `docker compose logs backend`. Las causas habituales son variables que faltan en `.env` o una base de datos que no está lista.
- **No veo mis cambios de código en Docker.** Arranca con `docker compose up --build --watch` (ver [Recarga en caliente](#recarga-en-caliente-en-docker)).
- **`pnpm gen:api` falla.** El backend debe estar arrancado con `ENVIRONMENT=development` en `http://localhost:8000`.
- **El login con los usuarios demo falla.** Comprueba que usas la contraseña de `DEMO_USER_PASSWORD` de tu `.env` y que el seed se ha ejecutado (`ENVIRONMENT=development`).
- **`uv` no se encuentra tras instalarlo.** Abre una terminal nueva para que se recargue el `PATH`.
- **Un cambio aparece como «El incidente ha cambiado» / «El recurso ha cambiado».** Otra persona (u otra pestaña) lo modificó mientras lo tenías abierto. Pulsa «Recargar» para ver la versión actual y vuelve a aplicar tu cambio.
- **El mapa aparece sin cartografía («Cartografía no disponible»).** El navegador no llega a `tiles.openfreemap.org` (sin conexión, proxy o cortafuegos). Las posiciones de los incidentes se siguen mostrando; la cartografía vuelve al recargar cuando haya conexión.
- **El mapa dice «Mapa no disponible».** El navegador no tiene WebGL2 (por ejemplo, con la aceleración por hardware desactivada). El resto del centro de mando funciona igual.
- **Los incidentes del seed no tienen coordenadas.** La base de datos se creó antes de la Fase 3: reiníciala con `docker compose down -v` (ver [Base de datos](#base-de-datos-migraciones-y-datos-demo)).
- **Los indicadores del centro de mando no se actualizan solos.** Es intencionado: todavía no hay tiempo real. Se refrescan tras cada cambio o con «Actualizar», y muestran la hora de los datos.
