# Arquitectura de Emergency Command

Estado: **Fase 4** (incidentes, recursos y centro de mando con datos reales, ubicaciones con PostGIS, mapa funcional, y asignación de recursos con ETA estimada), más el **rediseño visual del centro de mando** con el mapa como protagonista. Este documento describe lo que **está implementado**. Lo que pertenece a fases posteriores se indica expresamente como tal, y la [sección 15](#15-implementado-y-pendiente) separa con claridad lo que funciona de lo que solo está preparado.

Las reglas persistentes del proyecto (alcance, decisiones confirmadas, sistema de diseño) están en [`CLAUDE.md`](../CLAUDE.md). Este documento no las sustituye: explica cómo están implementadas.

> Emergency Command es un **prototipo de demostración**. No se conecta al 112, a servicios públicos ni a ninguna fuente real de datos. Todos los datos de demostración son ficticios y están marcados como simulados.

---

## 1. Visión general

```
┌────────────────────────── Navegador ───────────────────────────┐
│  React SPA (Vite)                                              │
│  · access token en memoria                                     │
│  · cookie httpOnly de refresh (no accesible desde JavaScript)  │
└───────────────┬────────────────────────────────────────────────┘
                │  HTTP, mismo origen: /api/* (proxy de Vite)
┌───────────────▼────────────────────────────────────────────────┐
│  Servidor Vite (frontend, :5173) ── proxy /api ──┐             │
└──────────────────────────────────────────────────┼─────────────┘
                                                   │
┌──────────────────────────────────────────────────▼─────────────┐
│  FastAPI (backend, :8000)                                      │
│  api/v1 → services → repositories → models (SQLAlchemy async)  │
└───────────────┬────────────────────────────────────────────────┘
                │  asyncpg
┌───────────────▼────────────────────────────────────────────────┐
│  PostgreSQL 18 + PostGIS 3.6 (db, :5432 en la red de Compose)  │
│  locations.geom geometry(Point, 4326) con índice GiST          │
└────────────────────────────────────────────────────────────────┘

Navegador ── estilo, teselas, fuentes y sprites ──► tiles.openfreemap.org
            (solo se piden teselas: nunca coordenadas ni datos de incidentes)
```

- El navegador **solo habla con el frontend**. Vite redirige `/api` al backend, de modo que la cookie de refresh es del mismo origen y no hacen falta peticiones cross-origin en el uso normal.
- El backend también tiene CORS configurado desde `.env` (orígenes explícitos, nunca `*`), para clientes que llamen a la API directamente.
- **Mapa base:** el navegador descarga directamente de OpenFreeMap el estilo `dark` y sus teselas. Los marcadores se dibujan en el navegador con los datos de la API: a OpenFreeMap no llega ningún dato de incidentes.
- La comunicación es **REST con JSON**. No hay WebSockets, Redis ni sondeo periódico de datos operativos (el tiempo real está previsto para la Fase 5).

---

## 2. Backend

### 2.1 Pila

Python 3.13, FastAPI, SQLAlchemy 2 (async) con asyncpg, Alembic, pydantic v2 con pydantic-settings, pwdlib (Argon2) y PyJWT. Las dependencias se gestionan con **uv** (`backend/pyproject.toml` y `uv.lock`). Calidad: ruff, mypy en modo estricto y pytest. La Fase 2 no añadió dependencias; la Fase 3 añadió **GeoAlchemy2** (solo el tipo `Geometry` y su integración con Alembic, sin Shapely).

### 2.2 Capas

```
app/
├─ main.py            create_app(): middleware CORS, manejadores de error, routers, lifespan
├─ api/
│  ├─ errors.py       excepciones de dominio → respuestas HTTP
│  └─ v1/             routers (sin lógica de negocio) + deps.py (dependencias)
├─ services/          lógica de negocio. No conocen HTTP
│                     auth, organizations, incidents, resources, dashboard, transactions
├─ repositories/      acceso a datos (consultas SQLAlchemy)
├─ models/            modelos SQLAlchemy, un fichero por entidad
├─ schemas/           modelos pydantic de entrada/salida
├─ domain/            reglas puras, sin I/O:
│                     enums, exceptions, incident_rules, incident_details, resource_rules, geo,
│                     eta, assignment_rules
├─ core/              config, security, permissions, logging
├─ db/                Base declarativa, motor y sesiones async
├─ realtime/          vacío: Fase 5
├─ simulation/        vacío: Fase 7
└─ ai/                vacío: Fase 8
```

Reglas que cumple el código:

- **Los routers no tocan la base de datos.** Validan la entrada, resuelven autenticación y permisos mediante dependencias y llaman a un servicio.
- **Los servicios no conocen HTTP.** No usan `Request` ni `HTTPException`; lanzan excepciones de dominio (`app/domain/exceptions.py`).
- **Las reglas de negocio son funciones puras** en `domain/` (transiciones de estado, esquemas de `details`, reglas de recursos). Las usan los servicios y también el seed, para que la demo nunca contenga datos que la API no permitiría.
- **La API devuelve códigos, no textos.** Todos los errores tienen la forma `{"detail": "<código>"}` (por ejemplo `invalid_transition` o `version_conflict`) y el frontend los traduce. La correspondencia con HTTP está en `app/api/errors.py`:

  | Excepción | HTTP | Ejemplos de código |
  |---|---|---|
  | `AuthenticationError` | 401 (con `WWW-Authenticate: Bearer`) | `invalid_credentials`, `invalid_token`, `refresh_token_reused` |
  | `PermissionDeniedError` | 403 | `permission_denied` |
  | `NotFoundError` | 404 | `incident_not_found`, `resource_not_found` |
  | `ConflictError` | 409 | `version_conflict`, `resource_code_taken`, `resource_already_assigned` |
  | `InvalidInputError` | 422 | `invalid_transition`, `invalid_details`, `incident_closed`, `resource_inactive`, `coordinates_incomplete`, `location_out_of_area`, `invalid_bbox`, `resource_not_available`, `resource_assigned`, `assignment_already_released`, `invalid_release_reason` |
  | otro `DomainError` | 400 | |
  | interbloqueo o fallo de serialización de PostgreSQL (`40P01`, `40001`) | 409 `concurrent_update`: no se ha guardado nada | |
  | error no controlado | 500 `internal_error`, sin detalles | |

  Los errores de validación de pydantic (formato de la petición) son 422 con el formato de FastAPI (`detail` es una lista con `type`, `loc` y `msg`), pero **sin `input` ni `ctx`**: no se devuelven los valores recibidos (pueden ser datos sensibles, como coordenadas) y un `NaN` en el cuerpo no rompe la respuesta. El frontend los trata como `validation_error`.

- **Una sesión de base de datos por petición** (`get_session`). Los servicios deciden cuándo hacer commit, siempre a través de `services/transactions.commit_or_conflict`, que traduce un conflicto de versión a `version_conflict`.

### 2.3 Endpoints

Todos bajo `/api/v1`. «Autenticado» exige un access token válido; los permisos se describen en la [sección 9](#9-autorización-rbac).

| Método y ruta | Acceso | Descripción |
|---|---|---|
| `GET /health` | público | Estado del backend y de la base de datos: `200 {"status":"ok","database":"ok"}`, o `503` con `degraded`/`unavailable` |
| `POST /auth/login` | público | Email y contraseña → access token en el cuerpo y refresh token en cookie |
| `POST /auth/refresh` | público (cookie) | Rota el refresh token y devuelve un access token nuevo |
| `POST /auth/logout` | autenticado | Revoca la sesión actual y borra la cookie |
| `GET /auth/me` | autenticado | Usuario, rol, permisos y organización |
| `GET /organizations` | `organizations:read` | Listado de organizaciones |
| `GET /incident-types` | `incidents:read` | Catálogo de tipos de incidente |
| `GET /incidents` | `incidents:read` | Listado paginado. Filtros: `status`, `priority` (repetibles), `type`, `active` (por defecto solo activos), `q` (código o título), `parent_id`, `has_coordinates`. Orden: `priority`, `-reported_at`, `reported_at`, `-updated_at` |
| `GET /incidents/map` | `incidents:read` | Incidentes con coordenadas como `FeatureCollection` GeoJSON ([sección 4.7](#47-ubicación-y-mapa)). Filtros: `status`, `priority`, `active`, `bbox`. **No sustituye al listado** |
| `POST /incidents` | `incidents:create` (+ `incidents:update` para indicar la prioridad o el incidente padre) | Alta. Empieza en `received`; sin prioridad, usa la del tipo. Sin `incidents:update`, indicar una prioridad o un padre responde 403 `field_not_permitted` y no se crea nada |
| `GET /incidents/{id}` | `incidents:read` | Detalle con padre, hijos y `allowed_transitions` |
| `PATCH /incidents/{id}` | `incidents:update_operational` (+ `incidents:update` para campos no operativos) | Edición parcial con `version` obligatoria. Con solo la edición operativa, enviar prioridad, título o padre rechaza la petición entera: 403 `field_not_permitted`, sin cambios ni eventos |
| `POST /incidents/{id}/status` | `incidents:change_status` (+ `incidents:close` para cerrar o cancelar) | Cambio de estado con `version` y motivo opcional |
| `GET /incidents/{id}/events` | `incidents:read` | Historial del incidente en orden cronológico |
| `POST /incidents/{id}/notes` | `incidents:annotate` | Nota en el historial (también en incidentes cerrados o cancelados) |
| `GET /resource-types` | `resources:read` | Catálogo de tipos de recurso |
| `GET /resources` | `resources:read` | Listado paginado con la asignación actual de cada recurso. Filtros: `status`, `type`, `organization_id`, `municipality` (de la base), `active`, `q`. Orden: `code`, `status`, `-status_changed_at` |
| `POST /resources` | `resources:manage` | Alta de un recurso |
| `GET /resources/{id}` | `resources:read` | Ficha del recurso |
| `PATCH /resources/{id}` | `resources:manage` | Edición de la ficha, incluida la (des)activación, con `version` |
| `POST /resources/{id}/status` | `resources:update_status` + ámbito de escritura | Cambio de estado operativo con `version`. Recurso de una organización fuera del ámbito: 403 `organization_out_of_scope` (antes que la versión) |
| `GET /incidents/{id}/assignments` | `incidents:read` | Asignaciones del incidente: activas primero y después el historial ([sección 5.1](#51-asignación-de-recursos-y-eta)) |
| `GET /incidents/{id}/assignment-candidates` | `incidents:read` + `resources:read` | Recursos asignables **del ámbito de escritura del usuario** (filtrado en la consulta), ordenados por ETA estimada, con los tipos sugeridos marcados. Filtros: `type`, `organization_id`, `include_assigned`. **Sin preselección** |
| `POST /incidents/{id}/assignments` | `assignments:manage` + ámbito de escritura sobre el recurso | `{resource_id, version, reassign?}` → detalle del incidente. Recurso fuera del ámbito (también al reasignar): 403 `organization_out_of_scope` |
| `POST /assignments/{id}/arrival` | `assignments:update` + ámbito de escritura sobre el recurso | Marca «en el lugar» (`{version}` del incidente). Recurso fuera del ámbito: 403 `organization_out_of_scope` |
| `POST /assignments/{id}/release` | `assignments:manage` + ámbito de escritura sobre el recurso | Retira con motivo (`{version, reason}`). Recurso fuera del ámbito: 403 `organization_out_of_scope` |
| `GET /dashboard/summary` | `incidents:read` + `resources:read` | KPIs del centro de mando ([sección 7](#7-resumen-del-centro-de-mando)) |

**Protegido por defecto:** `app/api/v1/router.py` registra los endpoints públicos uno a uno y cuelga el resto de un router que exige un access token válido. Un test recorre el esquema OpenAPI y comprueba que cualquier ruta no pública responde 401 sin token.

`/docs` y `/openapi.json` solo existen con `ENVIRONMENT=development`.

### 2.4 Configuración y logging

- `core/config.py` (pydantic-settings) lee las variables de entorno y el `.env` de la raíz. Con `ENVIRONMENT=production` el backend no arranca si la clave JWT o la contraseña de la base de datos conservan los valores de ejemplo, o si la cookie de refresh no es `Secure`.
- `core/logging.py` aplica a todos los handlers (también los de uvicorn) un filtro que tapa contraseñas, `Bearer …`, JWT, tokens y cookies. Además, el motor de SQLAlchemy usa `hide_parameters=True`, y los errores no controlados se registran solo con su tipo, sin el mensaje.

---

## 3. Modelo de datos

Seis migraciones en `backend/alembic/versions/`:

| Migración | Contenido |
|---|---|
| `20261007_2c90a9ee7694` (Fase 1) | `CREATE EXTENSION postgis`; tablas `roles`, `organizations`, `users`, `refresh_tokens`; los tres roles |
| `20261007_48bc2488f9e1` (Fase 2) | Catálogos `incident_types` y `resource_types` con sus datos de referencia; `incidents` con la secuencia `incident_code_seq`; `incident_events` con su trigger de solo inserción; `resources` |
| `20261008_16ed0556ad5c` (Fase 3) | `locations` con `geom geometry(Point, 4326)` e índice GiST; traslado del municipio y la descripción de cada incidente a su ubicación (sin tocar `version`, `updated_at` ni el historial); `incidents.location_id NOT NULL UNIQUE`. El `downgrade` restaura el texto y pierde las coordenadas |
| `20261008_22b43ff4025b` (Fase 3) | Amplía el CHECK de `incident_events.event_type` con `location_changed`. El `downgrade` se niega si ya hay eventos de ese tipo (el historial no se puede reescribir) |
| `20261009_3ba873c38add` (Fase 4) | `resource_types.average_speed_kmh` (velocidades de la ETA, cargadas en la migración); base de cada recurso en `locations` (`resources.base_location_id NOT NULL UNIQUE`), con traslado del municipio. El `downgrade` pierde las coordenadas de las bases |
| `20261009_e5df184e14c9` (Fase 4) | `resource_assignments` con el índice único parcial `uq_resource_assignments_active_resource` (una asignación activa por recurso); CHECK de `event_type` con `resource_assigned`, `resource_arrived` y `resource_released`. El `downgrade` se niega si ya hay asignaciones o eventos de asignación |

### 3.1 Tablas de la Fase 1

```
roles                      organizations                 users
─────────────────────      ─────────────────────────     ──────────────────────────────
id          uuid PK        id            uuid PK         id               uuid PK
code        varchar(32)    code          varchar(64) U   email            varchar(254) U
            U + CHECK      name          varchar(200)                     CHECK = lower(email)
            (admin |       is_active     bool            full_name        varchar(200)
             coordinator | is_simulated  bool            password_hash    varchar(255)  (Argon2)
             operator)     created_at    timestamptz     role_id          uuid FK → roles (RESTRICT)
created_at  timestamptz    updated_at    timestamptz     organization_id  uuid FK → organizations
                                                                          (RESTRICT, nullable)
                                                         is_active        bool
refresh_tokens                                           last_login_at    timestamptz NULL
───────────────────────────────────────────────          created_at / updated_at timestamptz
id              uuid PK
user_id         uuid FK → users (CASCADE)
family_id       uuid        (una familia = una sesión)
token_hash      varchar(64) U   (SHA-256 del token; nunca el token)
expires_at      timestamptz
revoked_at      timestamptz NULL
replaced_by_id  uuid FK → refresh_tokens (SET NULL)
created_at      timestamptz
```

### 3.2 Tablas de la Fase 2

```
incident_types                          resource_types
──────────────────────────────────      ─────────────────────────
id                     uuid PK          id          uuid PK
code                   varchar(64) U    code        varchar(64) U
category               varchar + CHECK  category    varchar + CHECK
icon                   varchar(64)      icon        varchar(64)   (nombre de Lucide)
default_priority       varchar + CHECK  is_active   bool
suggested_resource_types varchar[]      created_at  timestamptz
common_risks           varchar[]
details_schema_key     varchar NULL
is_active              bool
created_at             timestamptz

incidents                                          incident_events  (solo inserción)
────────────────────────────────────────────       ─────────────────────────────────────
id                  uuid PK                        id             uuid PK
code                varchar(20) U  INC-000123      incident_id    uuid FK → incidents (RESTRICT)
type_id             uuid FK → incident_types       event_type     varchar + CHECK
title               varchar(200)                   occurred_at    timestamptz
description         text NULL                      actor_user_id  uuid FK → users NULL (nulo = sistema)
status              varchar + CHECK                payload        jsonb (códigos y valores)
priority            varchar + CHECK                is_simulated   bool
location_id         uuid FK → locations U (1:1)
                                                   resources
affected_people     int NULL (≥ 0)                 ─────────────────────────────────────
details             jsonb  ('{}' por defecto)      id                 uuid PK
parent_incident_id  uuid FK → incidents NULL       code               varchar(32) U  (inmutable)
created_by_id       uuid FK → users NULL           name               varchar(200)
is_simulated        bool                           type_id            uuid FK → resource_types
version             int  (bloqueo optimista)       organization_id    uuid FK → organizations
reported_at         timestamptz                    status             varchar + CHECK
closed_at           timestamptz NULL               status_changed_at  timestamptz
created_at / updated_at timestamptz                municipality       varchar(100)
                                                   is_active          bool
                                                   is_simulated       bool
                                                   version            int  (bloqueo optimista)
                                                   created_at / updated_at timestamptz
```

Índices: estado, prioridad, tipo, padre y fecha de notificación de incidentes (más un índice parcial para los activos); `(incident_id, occurred_at)` en el historial; tipo, organización y estado en recursos.

### 3.3 Tablas de la Fase 3

```
locations  (una por incidente; solo la usa `Incident`)
────────────────────────────────────────────────────────
id            uuid PK
municipality  varchar(100)            obligatorio
description   varchar(255) NULL
geom          geometry(Point, 4326) NULL   NULL = sin coordenadas
created_at / updated_at timestamptz
índice GiST ix_locations_geom
```

- **1:1 con el incidente** (`incidents.location_id NOT NULL UNIQUE`, `ON DELETE RESTRICT`). No se comparten ubicaciones: corregir el punto de un incidente nunca mueve otro.
- **Latitud y longitud** no tienen columnas propias: se leen de `geom` con `ST_Y`/`ST_X` (`column_property`). El tipo `geometry(Point, 4326)` rechaza otras geometrías y otros SRID; un punto sin SRID recibe el de la columna.
- Desde la Fase 4, `locations` también guarda la **base de cada recurso** (`resources.base_location_id NOT NULL UNIQUE`). Una fila nunca se comparte: pertenece a un incidente o a un recurso.

### 3.4 Tablas de la Fase 4

```
resource_assignments  (nunca se borra; activa = released_at IS NULL)
──────────────────────────────────────────────────────────────────
id               uuid PK
incident_id      uuid FK → incidents (RESTRICT)
resource_id      uuid FK → resources (RESTRICT)
assigned_at      timestamptz         assigned_by_id  uuid FK → users NULL
arrived_at       timestamptz NULL    «en el lugar»
released_at      timestamptz NULL    released_by_id  uuid FK → users NULL
release_reason   varchar + CHECK NULL  completed | not_needed | unavailable |
                                       reassigned | incident_closed
eta_minutes      int NULL            estimación guardada al asignar
eta_distance_km  numeric(6,1) NULL
eta_origin       varchar + CHECK NULL  base (Fase 5: last_position)
is_simulated     bool
UNIQUE parcial (resource_id) WHERE released_at IS NULL
```

`resource_types` gana `average_speed_kmh` (`CHECK > 0`) y `resources` sustituye `municipality` por `base_location_id`.

### 3.5 Detalles comunes

- **Fechas:** todas son `timestamptz` en UTC. `db/base.py` lo impone para cualquier `datetime` y un test lo comprueba. El frontend las muestra en Europe/Madrid.
- **Claves primarias:** UUID, generado en Python (`uuid4`) con valor por defecto en el servidor (`gen_random_uuid()`) para las inserciones en SQL.
- **Enums como `varchar` + `CHECK`**, no como `ENUM` nativo: añadir un valor no exige `ALTER TYPE`.
- **Nombres de restricciones** deterministas (`pk_…`, `uq_…`, `fk_…`, `ck_…`, `ix_…`), para que las migraciones sean estables.
- **Relaciones:** con `lazy="raise"`. En async no hay carga perezosa implícita y los repositorios cargan las relaciones de forma explícita.
- **Datos de referencia en las migraciones:** roles y catálogos de tipos existen en todos los entornos; no son datos de demostración.
- **Sin borrados:** los incidentes se cancelan y los recursos se desactivan (`is_active`). No hay endpoints `DELETE`.
- **Una sola columna geográfica:** `locations.geom`. Un test de metadatos falla si aparece cualquier otra columna `geometry`/`geography`.
- **Alembic:** fija `search_path=public` (la imagen de PostGIS añade `tiger` y `topology`), ignora `spatial_ref_sys`, y `alembic check` confirma que modelos y migraciones coinciden.

---

## 4. Incidentes

### 4.1 Tipos, estados y prioridades

- **Tipos:** catálogo en base de datos (10 tipos: incendio forestal, incendio en edificio, accidente de tráfico, emergencia sanitaria, rescate en montaña, rescate acuático, inundación, fenómeno meteorológico adverso, mercancías peligrosas y desprendimiento). Cada tipo guarda su categoría, icono de Lucide, prioridad por defecto, tipos de recurso sugeridos, riesgos frecuentes y, si procede, la clave de su esquema de `details`. La API devuelve códigos; los nombres están en `es.json`.
- **Estados y prioridades:** enums fijos en código (`domain/enums.py`), comunes a todos los tipos.

### 4.2 Ciclo de vida

```
received ─► assessing ─► in_progress ─► controlled ─► closed
                              ▲              │
                              └──────────────┘   (reapertura)

received / assessing ──(primer recurso asignado, automático)──► resources_assigned
resources_assigned   ──(se retira el último, automático)──────► assessing
resources_assigned   ──(manual)──► in_progress

cancelled: desde received, assessing, resources_assigned o in_progress
```

- `resources_assigned` **nunca es una acción manual**: solo se alcanza asignando recursos. Los cambios automáticos se registran como `status_changed` con `cause: "assignment"`.

- La tabla de transiciones está en `domain/incident_rules.py` y es la **única fuente de verdad**. El detalle del incidente incluye `allowed_transitions`, calculado con esa misma tabla, para que el frontend ofrezca acciones sin duplicar el flujo.
- **Cerrar o cancelar** exige además el permiso `incidents:close`, y fija `closed_at`.
- **Un incidente cerrado o cancelado** no admite edición ni cambios de estado, pero **sí notas**: las notas no tocan datos operativos ni `version`.

### 4.3 Incidente padre

Un solo nivel: un incidente con padre no puede tener hijos, y un incidente con hijos no puede pasar a ser hijo. Cerrar el padre no se bloquea por tener hijos activos, ni cierra los hijos automáticamente.

### 4.4 Datos específicos del tipo (`details`)

- Cada `details_schema_key` tiene un modelo pydantic en `domain/incident_details.py` (`wildfire`: superficie afectada y vegetación; `flood`: nivel del agua).
- Un tipo sin esquema exige `details = {}` (`details_not_allowed`).
- `details` nunca contiene datos que se filtren, ordenen o agreguen con frecuencia (esos van en columnas propias), ni datos personales.

### 4.5 Historial (`IncidentEvent`)

`incident_events` es el **historial funcional** del incidente y la fuente del timeline. No es el sistema de auditoría de seguridad.

| `event_type` | `payload` |
|---|---|
| `incident_created` | `status`, `priority`, `type`, `parent` |
| `status_changed` | `from`, `to`, `reason` opcional |
| `priority_changed` | `from`, `to` |
| `incident_updated` | `fields` (lista de campos modificados; desde la Fase 3, la ubicación va en `location_changed`) |
| `note_added` | `text` |
| `parent_changed` | `from`, `to` (códigos de incidente o nulo) |
| `location_changed` | `fields` (`municipality`, `description`, `coordinates`), `from` y `to` (municipio, descripción, latitud y longitud) |
| `resource_assigned` | `resource` (código), `resource_id`, `resource_type`, `eta` (`{minutes, distance_km, origin}` o nulo), `eta_unavailable`, `reassigned_from` |
| `resource_arrived` | `resource`, `resource_id` |
| `resource_released` | `resource`, `resource_id`, `reason`, `reassigned_to` |

- Cada cambio inserta su evento **en la misma transacción** que el propio cambio: el historial no puede desincronizarse del incidente.
- **Solo inserción**, también en la base de datos: un trigger impide `UPDATE`, `DELETE` y `TRUNCATE`.
- El `payload` lleva códigos y valores; el frontend compone la frase traducida.
- `actor_user_id` nulo significa que el evento lo generó el sistema (por ejemplo, el seed); la interfaz lo muestra como «Sistema».
- **Una edición sin cambios reales no escribe nada:** ni evento ni incremento de `version`.
- Las coordenadas de `location_changed` forman parte del historial protegido por `incidents:read`, pero **nunca llegan a los logs** de la aplicación, a los mensajes de excepción ni a las trazas.

### 4.6 Concurrencia

- **Bloqueo optimista con `version`:** toda escritura (edición, cambio de estado) envía la `version` que leyó. Si no coincide, responde `409 version_conflict` sin efectos. No existe «gana el último».
- **`SELECT … FOR UPDATE`** sobre la fila al modificarla: dos cambios simultáneos se serializan.
- **Validar antes de modificar:** los servicios hacen todas las consultas de validación (padre, tipo, organización) antes de tocar el objeto, para que un autoflush no emita un `UPDATE` intermedio y `version` suba exactamente una vez por petición.
- **Códigos legibles** (`INC-000123`) de una única secuencia PostgreSQL, compartida por incidentes reales y simulados; `is_simulated` distingue el origen.
- **La ubicación también está cubierta:** vive en otra tabla, así que al cambiarla el servicio toca la fila del incidente para que `version` suba (una sola vez) y el bloqueo optimista la proteja.

### 4.7 Ubicación y mapa

- **En la API**, el incidente lleva `location: {municipality, description, latitude, longitude}`. En el alta es obligatoria (con coordenadas opcionales); en una edición se envía **completa** y sustituye a la anterior (omitir las coordenadas las borra).
- **Coordenadas WGS84** en grados decimales (`domain/geo.py`):
  - latitud en [-90, 90] y longitud en [-180, 180], sin `NaN` ni infinitos, redondeadas a 6 decimales (≈ 11 cm);
  - ambas o ninguna (`coordinates_incomplete`);
  - dentro del **área de la demo**, Asturias con margen (`location_out_of_area`). Es una protección de la demo, no geofencing: detecta sobre todo latitud y longitud intercambiadas.
- **Orden de coordenadas:** la API habla de `latitude`/`longitude`; GeoJSON, WKT y PostGIS usan `[longitud, latitud]`. La conversión solo se hace en el modelo (`models/location.py`), en el filtro por rectángulo y en la respuesta GeoJSON.
- **`GET /incidents/map`:** `FeatureCollection` con un `Point` y propiedades mínimas por incidente (`id`, `code`, `title`, `status`, `priority`, `type_code`, `type_icon`, `is_simulated`), más urgentes primero. Miembros propios: `unlocated_total` (cumplen los filtros pero no tienen coordenadas; no depende del `bbox`) y `truncated` (tope de 1.000 elementos, sin paginación).
- **Única consulta espacial:** `bbox=minLon,minLat,maxLon,maxLat` filtra con `geom && ST_MakeEnvelope(…, 4326)`, que usa el índice GiST. Un rectángulo inválido es `422 invalid_bbox`.
- **Incidentes sin coordenadas:** son un caso normal. Siempre tienen municipio, se cuentan en el mapa, se pueden filtrar en el listado (`has_coordinates=false`) y las coordenadas se pueden añadir al editar.

---

## 5. Recursos

- **Ficha:** código, nombre, tipo, organización, **base** (`Location`: municipio, descripción y coordenadas opcionales), estado, `status_changed_at`, asignación actual, `is_active`, `is_simulated` y `version`. Sin historial de estados: solo se guarda el último cambio (las asignaciones guardan el suyo). La posición actual/GPS es de la Fase 5.
- **Código inmutable:** se normaliza a mayúsculas y es único (`409 resource_code_taken`).
- **Estados operativos:** `available`, `in_service`, `out_of_service`. Se puede pasar de cualquiera a cualquier otro; repetir el actual es `422 invalid_transition` (`domain/resource_rules.py`).
- **Desactivación:** `is_active = false` por `PATCH`. Un recurso desactivado no cambia de estado (`422 resource_inactive`) hasta que se reactive, pero su ficha sí se puede editar.
- **Tipo y organización nuevos** deben estar activos; un recurso puede seguir asociado a uno que se desactivó después.
- **Bloqueo optimista** con `version`, igual que en incidentes.
- **Recurso asignado:** su estado lo gobierna la asignación. No se puede cambiar a mano ni desactivar (`422 resource_assigned`): se retira desde el incidente.

### 5.1 Asignación de recursos y ETA

**Principio: el sistema informa → la persona responsable decide → el sistema ejecuta.** Los candidatos se ordenan por ETA estimada y se marcan los tipos sugeridos por el catálogo, pero **nunca se preselecciona ni se asigna nada automáticamente** (eso no es IA; la IA es de la Fase 8).

- **ETA estimada** (`domain/eta.py`), local y determinista, sin APIs externas ni rutas: `minutos = ceil(haversine × 1,4 / velocidad media del tipo × 60)`. `distance_km` es la distancia estimada por carretera (línea recta × 1,4), con 1 decimal; `origin` es `base`. Sin tiempo de activación. Velocidades (km/h): autobomba 50, rescate 55, ambulancia básica 60, avanzada 65, mando 60, protección civil 50, logística 45.
- **Se guarda al asignar** (`eta_*`): cambiar después la base o la velocidad no altera lo registrado. La interfaz siempre la muestra como «estimado».
- **Una asignación activa por recurso** (índice único parcial; con dos asignaciones simultáneas, una gana y la otra recibe `409 resource_already_assigned`). Un incidente admite varios recursos.
- **Asignar:** incidente activo con su `version`, recurso activo y `available`. En una transacción: recurso → `in_service`, asignación con ETA, `resource_assigned` y, si el incidente estaba en `received`/`assessing`, `resources_assigned`. Orden global de bloqueos, igual en todas las operaciones (también al cerrar un incidente): **incidentes (por id) → recursos (por id) → asignaciones**. Reasignar mira primero, sin bloquear, a qué incidente está asignado el recurso, bloquea los dos incidentes en orden y lo vuelve a comprobar todo con los bloqueos tomados.
- **«En el lugar»:** rellena `arrived_at` una vez; **no cambia el estado del incidente**.
- **Retirar:** motivo obligatorio (`completed`, `not_needed`, `unavailable`; los otros dos los pone el sistema). El recurso vuelve a `available` (o `out_of_service` con `unavailable`). Si era el último y el incidente seguía en `resources_assigned`, vuelve a `assessing`.
- **Reasignar** (`reassign: true`, confirmado en la interfaz): retira del incidente de origen (`reassigned`) y asigna al de destino en la misma transacción, con eventos y reglas en ambos.
- **Cerrar o cancelar** un incidente retira automáticamente sus asignaciones activas (`incident_closed`); la confirmación enumera los recursos.
- **Toda escritura** sube una vez la `version` del incidente (y la del recurso cuando cambia su estado) y devuelve el detalle del incidente.
- **Preparado para la Fase 5:** todo cambio de asignación genera su `IncidentEvent` desde un servicio (el EventBus solo tendrá que publicarlos tras el commit), y `origin` permite estimar desde una posición actual (`resource_positions`, solo diseñada). Hueco conocido: los cambios manuales de estado de un recurso no generan evento.

---

## 6. Datos simulados y datos reales

- **Ubicación:** los datos de demostración viven **solo** en `backend/seeds/` (`fixtures.py`, `seed.py` y `operational.py`). No hay datos falsos en componentes, servicios ni routers.
- **Contenido:**

  | Datos | Cantidad | Marcado |
  |---|---|---|
  | Organizaciones | 4 (coordinación Asturias, bomberos Oviedo, sanitario Gijón, protección civil Avilés) | `is_simulated`, código `sim-…`, «(simulado)» en el nombre |
  | Usuarios | 5: admin y coordinador (coordinación Asturias) y tres operadores, de bomberos Oviedo, de sanitario Gijón y sin organización, para mostrar el ámbito organizativo | email del dominio reservado `.test` |
  | Recursos | 18 (11 disponibles, 5 en servicio, 2 fuera de servicio) | `is_simulated`, código `SIM-…`, «(simulado)» en el nombre |
  | Incidentes | 12 en Oviedo, Gijón, Avilés, Siero, Mieres y Aller: todas las prioridades y estados alcanzables, 2 cerrados, 1 cancelado y un temporal con dos incidentes hijos | `is_simulated`, «(simulado)» en el título, ubicación genérica «(ubicación simulada)». Coordenadas aproximadas (3 decimales, ≈ 100 m) en zonas genéricas, nunca sobre instalaciones de emergencias; dos incidentes activos sin coordenadas a propósito |
  | Eventos del historial | 38, coherentes con el estado final de cada incidente | `is_simulated`, actor nulo («Sistema») |

  Ningún teléfono, dirección, indicativo, URL ni nombre corresponde a un servicio real.

- **Solo en desarrollo:** el seed se niega a ejecutarse fuera de `ENVIRONMENT=development`. La contraseña de los usuarios demo sale de `DEMO_USER_PASSWORD`.
- **Idempotente**, con un cerrojo consultivo de PostgreSQL para que dos ejecuciones no se pisen:
  - **usuarios y organizaciones:** crea lo que falta y devuelve lo existente al estado de los fixtures;
  - **recursos e incidentes:** ids fijos derivados de una clave del fixture (UUIDv5); **solo crea lo que falta y nunca modifica lo existente**. El seed no es una herramienta de sincronización ni de restauración: lo que se cambie durante una demo se conserva. Repetirlo no consume números de la secuencia `INC-`.
- **Mismas reglas que la API:** cada historial se valida con `can_transition`, cada `details` con su esquema y cada punto con `validate_coordinates`; un fixture incoherente hace fallar el seed sin escribir nada.
- **Bases de datos anteriores a la Fase 3:** como el seed no modifica lo existente, sus incidentes se quedan sin coordenadas. Para tener los datos demo con coordenadas hay que reiniciar la base de datos (`docker compose down -v`).
- **Horas relativas** al momento de la ejecución que crea cada fila. En los incidentes del seed, `created_at` coincide con `reported_at` y `updated_at` con el último evento.
- El simulador previsto para la Fase 7 operará a través de los servicios (nunca escribiendo directamente en la base de datos) y marcará sus datos con `is_simulated = true`. **No existe todavía.**

---

## 7. Resumen del centro de mando

`GET /dashboard/summary` agrega con consultas sobre los datos actuales (`services/dashboard.py`):

| Bloque | Campos |
|---|---|
| `incidents` | `active_total`; `by_priority` y `by_status` (solo activos, con todas las claves aunque valgan 0); `affected_people` (suma en activos); `reported_last_24h` (notificados en 24 h, **en cualquier estado**) |
| `resources` | `active_total` y `by_status` (solo recursos activos); `inactive_total` |
| `generated_at` | Momento del cálculo |

Es una **instantánea**: no hay tiempo real ni sondeo. El frontend la vuelve a pedir tras cada escritura o con «Actualizar», y muestra su hora («Datos de las 00:32:46»).

---

## 8. Autenticación

### 8.1 Tokens

| | Access token | Refresh token |
|---|---|---|
| Formato | JWT HS256 | Valor opaco aleatorio de 256 bits (`secrets.token_urlsafe(32)`) |
| Duración | `ACCESS_TOKEN_EXPIRE_MINUTES` (15 por defecto) | `REFRESH_TOKEN_EXPIRE_DAYS` (7 por defecto) |
| Dónde viaja | Cuerpo de la respuesta → cabecera `Authorization: Bearer` | Cookie `ec_refresh_token`: `HttpOnly`, `SameSite=Lax`, `Path=/api/v1/auth`, `Secure` según `REFRESH_COOKIE_SECURE` |
| Dónde se guarda en el cliente | Solo en memoria (variable de módulo) | Solo en la cookie; JavaScript no puede leerla |
| En el servidor | Sin estado | Solo su hash SHA-256 en `refresh_tokens` |

El access token incluye `sub` (id de usuario), `iss`, `aud`, `iat`, `exp`, `jti` y `typ=access`. Al validarlo se exigen todos salvo `jti`, con 10 s de tolerancia de reloj. En cada petición protegida se carga el usuario de la base de datos, así que desactivar a un usuario le corta el acceso al momento.

Las contraseñas se guardan con Argon2 (pwdlib). Si el email no existe, se verifica igualmente contra un hash ficticio, para que el tiempo de respuesta no revele qué emails están registrados. Tanto el email inexistente como la contraseña incorrecta responden `invalid_credentials`.

### 8.2 Rotación y detección de reutilización

```
login ─► token A (familia F)
refresh(A) ─► A revocado, A.replaced_by = B ─► token B (familia F)
refresh(B) ─► …

refresh(A) de nuevo:
  · dentro de 10 s desde su rotación → 401 refresh_token_rotated
      (carrera benigna entre pestañas: la cookie ya contiene B; la familia sigue viva)
  · pasado ese margen               → 401 refresh_token_reused
      (posible robo: se revoca toda la familia F y la sesión queda invalidada)
```

- La consulta del token usa `SELECT … FOR UPDATE`, así que dos refresh simultáneos con el mismo token se serializan.
- **Logout:** revoca la familia de la sesión actual (no las de otros dispositivos del mismo usuario) y solo si pertenece al usuario autenticado.
- **Tras el logout,** el access token sigue siendo válido hasta que caduca (JWT sin estado), pero el frontend lo descarta de la memoria.

### 8.3 Ciclo completo en el frontend

1. **Al cargar la aplicación** no hay access token en memoria. La sesión se restaura con `POST /auth/refresh` (cookie) y después `GET /auth/me`. Si el refresh responde 401, no hay sesión y se muestra el login.
2. **Login:** `POST /auth/login`, luego `GET /auth/me`. El usuario y sus permisos quedan en la caché de TanStack Query.
3. **Peticiones:** el cliente añade `Authorization: Bearer <token>`.
4. **401 en una petición protegida:** se hace un único refresh y un único reintento ([sección 10.4](#104-cliente-api-y-estrategia-de-refresh)).
5. **Logout:** `POST /auth/logout`. Pase lo que pase, después se borran el token en memoria y la caché, y se vuelve al login.

---

## 9. Autorización (RBAC)

- **Fuente de verdad en el backend.** Los roles están en la tabla `roles` y el mapa de rol a permisos está en el código, en `app/core/permissions.py`:

  | Permiso | `admin` | `coordinator` | `operator` |
  |---|:-:|:-:|:-:|
  | `incidents:read` | ✅ | ✅ | ✅ |
  | `incidents:create` | ✅ | ✅ | ✅ |
  | `incidents:update` (edición completa de la ficha) | ✅ | ✅ | ❌ |
  | `incidents:update_operational` (descripción, personas afectadas, ubicación y `details`) | ✅ | ✅ | ✅ |
  | `incidents:annotate` (notas) | ✅ | ✅ | ✅ |
  | `incidents:change_status` (estado del incidente) | ✅ | ✅ | ❌ |
  | `incidents:close` (cerrar o cancelar; además de `incidents:change_status`) | ✅ | ✅ | ❌ |
  | `resources:read` | ✅ | ✅ | ✅ |
  | `resources:update_status` | ✅ | ✅ | ✅ |
  | `resources:manage` (alta, edición, desactivación) | ✅ | ❌ | ❌ |
  | `organizations:read` | ✅ | ✅ | ❌ |
  | `assignments:manage` (asignar, retirar, reasignar) | ✅ | ✅ | ❌ |
  | `assignments:update` (marcar «en el lugar») | ✅ | ✅ | ✅ |

- **Matriz aprobada** en `CLAUDE.md` §2.11 (etapa de roles, permisos y ámbito organizativo, en curso). El estado del incidente y el estado operativo de un recurso son permisos distintos: el operador no cambia el primero, pero sí el segundo.
- **Comprobación:** con la dependencia `require_permission(Permission.X)` en el router. Lo que depende del cuerpo de la petición se comprueba en el servicio: cerrar o cancelar (según el estado de destino), los campos no operativos de una edición (`OPERATIONAL_FIELDS` en `domain/incident_rules.py`; cuenta lo **enviado**, no lo que cambiaría, y se comprueba antes de leer o modificar nada) y la prioridad inicial y el incidente padre de un alta (`CREATE_FIELDS_REQUIRING_FULL_EDIT`; sin `incidents:update`, se aplican la prioridad del tipo y ningún padre). Sin permiso responde `403 {"detail":"permission_denied"}`. Un test de inventario (`tests/integration/test_permission_matrix.py`) declara los permisos de **cada ruta** de la API, la llama con los tres roles y falla si aparece una ruta sin declarar.
- **Ámbito organizativo (en construcción, `CLAUDE.md` §2.11).** `domain/access_scope.py` define `AccessScope`, inmutable, con un ámbito de lectura y otro de escritura («todas» o un conjunto de organizaciones), y `scope_for(rol, organización)` con una regla explícita por rol:

  | Rol | Lectura | Escritura |
  |---|---|---|
  | `admin`, `coordinator` | todas | todas |
  | `operator` con organización | todas | solo la suya |
  | `operator` sin organización | todas | ninguna |

  Un rol sin regla falla de forma cerrada (`PermissionDeniedError`, 403). La dependencia `get_access_scope` lo calcula para el usuario autenticado, sin consultas adicionales, y `OutOfScopeError` se traduce a `403 {"detail":"organization_out_of_scope"}`.

  **Dónde se aplica hoy:**
  - Cambio de estado operativo de un recurso.
  - «En el lugar».
  - Asignar, retirar y reasignar.
  - Candidatos de asignación: el repositorio filtra con `OrganizationAccess.as_filter()`, así que pedir otra organización con `organization_id` no salta el ámbito.

  Los servicios llaman a una única comprobación, `AccessScope.require_write(organización del recurso)`, nada más cargar el recurso y antes de modificar nada ni registrar eventos. Un recurso de otra organización da **403**, no 404: el operador puede verlo (D4) y el 404 se reserva para las lecturas fuera de ámbito (D5).

  **Lectura (R.6):**
  - Con D4, todos los roles leen todas las organizaciones, así que el ámbito de lectura **no restringe hoy a nadie**.
  - El patrón está aplicado a la ficha de un recurso (`AccessScope.require_read`, que fuera del ámbito responde 404 `resource_not_found`, como si no existiera, según D5) y al listado de recursos (filtro en la consulta, para que el total y la paginación cuadren).
  - Lecturas identificadas pero todavía sin filtro, hasta que exista un ámbito de lectura limitado y se decida cómo mostrarlas:
    - los recursos incluidos en las asignaciones de un incidente;
    - los recuentos de recursos del dashboard;
    - las bases en el mapa;
    - los códigos de recurso en el historial.
  - Los incidentes no tienen organización (D2): no se filtran.

  Hoy admin y coordinador alcanzan a todas las organizaciones (D1), así que en la práctica el ámbito solo restringe al operador. Los tests prueban además un ámbito restringido sustituyendo la dependencia, como preparación para una autorización por organización.

  **Excepción consciente:** cerrar o cancelar un incidente retira **todos** sus recursos asignados, sean de la organización que sean. Es una consecuencia de una acción sobre el incidente (`incidents:close`), no una escritura directa sobre esos recursos.
- **Ámbito en la interfaz (R.7).**
  - `/auth/me` incluye `scope`: `read` y `write`, cada uno como `{all_organizations, organization_ids}`. Lo calcula `scope_for` en el backend; la petición no tiene parámetros que lo alteren.
  - En el frontend, `canWriteOrganization(user, organizationId)` (`features/auth/hooks.ts`) es la única comprobación de ámbito. Con ella se muestran u ocultan los botones de estado de un recurso (fuera del ámbito, una línea explica por qué), «En el lugar» y «Retirar».
  - El alta del operador no ofrece incidente padre ni prioridad (D10 y D11).
- **En el frontend es solo experiencia de usuario.** `/auth/me` devuelve la lista de permisos del usuario, y con ella el frontend filtra la navegación, oculta las acciones no permitidas, evita peticiones que sabe que darían 403 (por ejemplo, la lista de organizaciones para el operador) y muestra «Acceso no permitido» en las rutas sin permiso. El backend vuelve a comprobarlo en cada petición.

---

## 10. Frontend

### 10.1 Pila

React 19, Vite 8 y TypeScript 6 en modo estricto. Además:

- **Estilos:** Tailwind CSS v4 y shadcn/ui sobre **Base UI**.
- **Datos y navegación:** TanStack Query y React Router.
- **i18n:** react-i18next.
- **Formularios:** zod con react-hook-form.
- **Iconos:** lucide-react.
- **Mapa:** MapLibre GL JS 6 (Fase 3), sin envoltorios de React.
- **Calidad:** ESLint (`strictTypeChecked`), Prettier y Vitest con Testing Library.
- **Gestor de paquetes:** pnpm. La Fase 2 no añadió dependencias; la Fase 3 añadió `maplibre-gl`.

### 10.2 Estructura

```
src/
├─ app/                  router, providers, query client, layout y rutas genéricas
│  ├─ layout/            AppShell, Sidebar (navegación por permisos, plegable a iconos),
│  │                     TopBar (identidad, aviso de demo, conexión y reloj)
│  ├─ routes/            ProtectedRoute, RequirePermission, 404, 403, error, carga
│  └─ dev/design-system/ catálogo de desarrollo (solo con import.meta.env.DEV)
├─ components/ui/        componentes de shadcn/ui (código de terceros, cambios mínimos)
├─ components/ops/       sistema de diseño propio (ver 10.6)
├─ features/
│  ├─ assignments/       asignación de recursos: api, hooks, panel y diálogo de asignación
│  ├─ auth/              sesión, login, permisos
│  ├─ command-center/    resumen del dashboard, filtros compartidos, paneles (mapa incluido)
│  │                     y columnas plegables (Dock)
│  ├─ incidents/         api, hooks, types, filters, form, presentation, components
│  ├─ resources/         api, hooks, types, filters, form, presentation, components
│  ├─ map/               MapLibre: configuración, mapas diferidos (lazy) y marcadores
│  ├─ organizations/     listado de organizaciones
│  └─ system/            health
├─ lib/                  api-client, query-keys, query-string, navigation, code-label,
│                        form-a11y, format, use-persisted-toggle, utils
├─ i18n/                 config + locales/es.json
├─ styles/               tokens.css (fuente de verdad del diseño) + index.css
├─ types/api.ts          generado desde OpenAPI (pnpm gen:api), no se edita a mano
└─ test/                 utilidades de test y backend falso en memoria
```

Cada módulo de `features/` sigue el mismo reparto: `types.ts` (alias de los tipos generados), `api.ts` (llamadas), `hooks.ts` (TanStack Query e invalidaciones), `filters.ts` y `form.ts` (lógica pura y testeable: URL ↔ parámetros, esquemas zod, payloads) y `presentation.ts` (código → tono, icono y mensaje de error).

### 10.3 Pantallas y rutas

| Ruta | Permiso | Contenido |
|---|---|---|
| `/login` | público | Inicio de sesión |
| `/` | sesión | **Centro de mando:** franja de KPIs, **mapa** de incidentes activos como zona principal, columna plegable de incidentes activos con filtros y columna plegable de detalle (incidente seleccionado con acciones de estado, **recursos asignados** con sus acciones, últimos 5 eventos y resumen de recursos por estado). Ver «Disposición del centro de mando» |
| `/incidents` | `incidents:read` | Listado con filtros (incluido «Coordenadas»), orden y paginación |
| `/incidents/new` | `incidents:create` | Alta con validación, coordenadas opcionales («Elegir en el mapa») y sección fija de `details` según el tipo |
| `/incidents/:id` | `incidents:read` | Detalle con minimapa, acciones de estado, edición, **recursos asignados** (asignar, en el lugar, retirar, reasignar), padre/hijos, historial y notas |
| `/resources` | `resources:read` | Listado con filtros, orden y paginación |
| `/resources/new` | `resources:manage` | Alta de recurso |
| `/resources/:id` | `resources:read` | Ficha con base y asignación actual, cambio de estado (bloqueado si está asignado), edición y desactivación |
| `/organizations` | `organizations:read` | Listado de organizaciones |
| `/dev/design-system` | solo desarrollo | Catálogo del sistema de diseño; no existe en producción |

Las páginas se cargan bajo demanda (`lazy`), así que el bundle inicial solo contiene el router, la sesión y el layout.

**Disposición del centro de mando** (rediseño posterior a la Fase 4, `CLAUDE.md` §2.10.1), pensada para monitores grandes de sala y para portátiles:

- **Barras de la aplicación:**
  - Barra superior de 40 px con identidad, aviso de demo, conexión y reloj.
  - Barra lateral plegable a iconos, con nombres accesibles y tooltip. Empieza plegada por debajo de 1536 px.
- **Indicadores:** franja de una línea con `KpiTile` compacto.
- **Mapa:** a sangre en el centro, sin cabecera ni pie. Recuento, avisos y leyenda van superpuestos en las esquinas (ver 10.7).
- **Columnas plegables (`Dock`) a los lados del mapa, no superpuestas:** al plegar una, el mapa recupera el espacio; plegada, queda un carril con su botón (`aria-expanded`). Desplegadas miden:
  - izquierda: 288 px (`lg`), 320 px (`xl`) y 384 px (`2xl`);
  - derecha: 320 px, 352 px y 416 px.
- **Columna izquierda:** incidentes activos en filas compactas (prioridad, código, estado, título, municipio, recursos asignados y hora). Toda la fila selecciona; la seleccionada lleva fondo y borde lateral.
- **Columna derecha:** incidente seleccionado (resumen y `IncidentStatusActions`), `AssignmentsPanel` (asignar, reasignar, «en el lugar», retirar), últimos eventos y resumen de recursos. Son los mismos componentes y comprobaciones de permisos que la ficha completa.
- **Selección:** seleccionar un incidente despliega la columna derecha si estaba plegada.
- **Desplazamiento:** la página no se desplaza; cada columna tiene su propio scroll. Por debajo de 1024 px las columnas se apilan (no es un diseño móvil).
- **Plegado:** es una preferencia local de cada navegador (`lib/use-persisted-toggle.ts`, `localStorage` con claves `ec.layout.*` y try/catch). No es estado compartible y no va en la URL. Las transiciones duran 150 ms y se desactivan con `prefers-reduced-motion`.

**Comportamientos comunes:**

- **Datos solo de la API.** Ninguna pantalla contiene datos de ejemplo; todo llega del backend y se marca «Simulado» cuando `is_simulated` es verdadero.
- **Estados** de carga, vacío, vacío por filtros y error con «Reintentar» en todos los paneles (`Panel`).
- **Estado en la URL:** filtros, orden, página y, en el centro de mando, el incidente seleccionado (`/?incident=…&priority=…`). Se pueden compartir y sobreviven a una recarga.
- **«Volver»** regresa a la pantalla de origen con sus filtros, página o selección (`lib/navigation.ts`).
- **Acciones según el backend:** los cambios de estado de un incidente salen de `allowed_transitions`; la interfaz no duplica el flujo.
- **Confirmaciones:** cerrar, cancelar (con motivo opcional) y desactivar piden confirmación, con el foco inicial en la opción de no hacer nada. Los cambios operativos frecuentes (por ejemplo, el estado de un recurso) no.
- **Conflictos:** un `409 version_conflict` muestra «El incidente/recurso ha cambiado» con «Recargar». Recargar descarta los cambios locales y muestra la versión actual; nunca se sobrescribe un cambio ajeno.
- **Sin cambios, sin llamada:** guardar una edición sin cambios no llama a la API.
- **Refresco:** tras cada escritura se invalidan listados, mapa, detalle y KPIs. No hay sondeo periódico ni tiempo real.

### 10.4 Cliente API y estrategia de refresh

`src/lib/api-client.ts` es el **único** lugar que gestiona tokens:

- **Access token:** en una variable de módulo. Nunca se guarda en `localStorage` ni en `sessionStorage`.
- **Refresh compartido:** si varias peticiones reciben 401 a la vez, comparten una sola petición de refresh (una promesa en vuelo).
- **Reintentos acotados**, sin bucles posibles:
  - la petición original se reintenta como máximo una vez tras un refresh correcto;
  - el refresh se repite como máximo una vez, y solo si el backend responde `refresh_token_rotated`;
  - la propia petición de refresh nunca dispara otro refresh.
- **Fallo definitivo** (el refresh responde 401): se borra el token, se avisa de «sesión expirada», la caché se vacía y las rutas protegidas llevan al login, recordando la página en curso.
- **Fallo transitorio** (red o 5xx en el refresh): no se cierra la sesión; se propaga el error.
- **Endpoints públicos** (`auth: false`, como login y health): un 401 no intenta refresh, porque en el login significa credenciales incorrectas.
- **Errores:** se exponen como `ApiError {status, code}`, donde `code` es el `detail` del backend, y `status` es 0 en los fallos de red. `isVersionConflict()` identifica el 409 de bloqueo optimista.
- **Logs:** el código de la aplicación no tiene ningún `console.*`.

**TanStack Query:** no reintenta los errores 4xx y reintenta como máximo 2 veces los de red y 5xx; no refresca al volver a la pestaña; las claves están centralizadas en `lib/query-keys.ts`, con prefijos (`incidents`, `resources`, `dashboard`) que permiten invalidar un área entera.

### 10.5 Tipos de la API

`pnpm gen:api` genera `src/types/api.ts` con openapi-typescript desde `http://localhost:8000/openapi.json`. Antes de escribir valida que el esquema es OpenAPI 3.x y contiene las rutas esperadas, y escribe en un temporal que renombra al final.

**Todos** los tipos de la API del frontend se importan de ahí, incluida la prioridad de incidente (`IncidentPriority`). El tipo manual `PriorityCode` de la Fase 1 se eliminó al existir `Incident.priority` en el backend: hay una sola fuente de verdad.

### 10.6 Sistema de diseño

Las reglas están en `CLAUDE.md` §7; `src/styles/tokens.css` las aplica:

- **Colores:** solo los tokens del proyecto, expuestos a Tailwind con `@theme`. Se elimina la paleta por defecto de Tailwind (`--color-*: initial`), así que no se pueden usar colores arbitrarios.
- **Estado:** seis colores (`critical`, `high`, `warning`, `ok`, `info`, `inactive`), cada uno con sus variantes de texto, fondo tenue y borde. El texto de `inactive` usa #9CA3AF para alcanzar el contraste AA.
- **Formas:** sin sombras (solo bordes), radios entre 4 y 6 px y filas de 32 px (`h-row`).
- **Tipografía:** Inter (texto base de 13 px, `text-sm`) y JetBrains Mono con cifras tabulares (`font-data`) para códigos, horas y cifras.
- **Movimiento:** la única animación es `critical-pulse`, que se desactiva con `prefers-reduced-motion`. Una regla global anula transiciones y animaciones de componentes de terceros.
- **Accesibilidad:** el color nunca va solo, siempre con icono y texto; el foco de teclado siempre es visible; los enlaces con aspecto de botón son enlaces reales (`<Link className={buttonVariants()}>`), no botones de Base UI con `render`, que se anunciarían como botón.

**Correspondencia de códigos con tonos** (cada estado tiene además su icono propio):

| Dominio | Código → tono |
|---|---|
| Prioridad de incidente | `critical` → critical · `high` → high · `medium` → warning · `low` → info |
| Estado de incidente | `received`, `assessing` → warning · `resources_assigned`, `in_progress` → info · `controlled` → ok · `closed`, `cancelled` → inactive |
| Estado de recurso | `available` → ok · `in_service` → info · `out_of_service` → warning · recurso desactivado → inactive |
| Dato simulado | info, con icono de matraz y el texto «Simulado» |

**Componentes de `components/ops/`:** `Panel` (estados de carga, vacío y error; `flush` para listas sin relleno), `PriorityBadge`, `StatusPill`, `SimulatedPill`, `KpiTile` (tarjeta o variante `compact` de una línea), `ConfirmDialog` (admite contenido adicional, como un motivo), `MutationErrorAlert` (errores de escritura y 409), `FilterSelect`, `Pagination`, `BackLink`, `DetailItem`/`DateTimeText`, `FormField`, `IncidentMarker` (marcador del mapa), `ResourceMarker` (bases de los recursos asignados) y `EtaText` (ETA siempre «estimado»).

**Catálogo:** `/dev/design-system` muestra los tokens y los componentes base en sus estados. Vite elimina esa ruta, su código y sus textos del build de producción.

### 10.7 Mapa

- **MapLibre GL JS + OpenFreeMap `dark`**, configurable con `VITE_MAP_STYLE_URL` (vacío = OpenFreeMap). Mapa plano, sin rotación ni inclinación. Encuadre inicial en Asturias. En el centro de mando, el zoom de MapLibre va arriba a la derecha y «Ajustar a incidentes» y «Centrar en Asturias» son botones de icono (con nombre accesible y tooltip) abajo a la derecha, sobre la atribución.
- **Carga diferida:** solo `features/map/use-maplibre.ts` y `map-parts.tsx` importan `maplibre-gl`, y se cargan dentro de componentes `lazy` (`features/map/lazy.ts`). El login y el resto de pantallas no descargan la librería. El worker de MapLibre 6 se publica como fichero propio (`?url` + `setWorkerUrl`).
- **Marcadores DOM** (`IncidentMarker`): botones accesibles, compactos para no solaparse a escala regional. Icono y color de prioridad, borde según el estado (discontinuo = sin intervenir, continuo = en intervención, con check = controlado). El código aparece al seleccionarlo y en el tooltip (ratón o foco); el nombre accesible incluye código, prioridad, estado y «Simulado». El crítico pulsa, salvo con `prefers-reduced-motion`. Una leyenda superpuesta abajo a la izquierda, plegada por defecto, explica la codificación.
- **Mapa ↔ lista ↔ panel:** la selección (`?incident=`) y los filtros de prioridad y estado viven en la URL y los comparten el mapa, la lista y el panel lateral. Seleccionar en la lista centra el mapa si el incidente no está a la vista, sin cambiar el zoom y sin animación con movimiento reducido. Lo mismo ocurre si el mapa cambia de tamaño (por ejemplo, al plegar o desplegar una columna) y la selección queda fuera de la vista. En el centro de mando no hay popup: el detalle está en el panel lateral.
- **Avisos superpuestos (centro de mando):** arriba a la izquierda, recuento de incidentes en el mapa, «Datos simulados», resultados truncados y error de carga con «Reintentar».
- **Incidentes sin coordenadas:** aviso con recuento y enlace al listado filtrado; indicador «Sin coordenadas» en listas, panel y ficha; aviso en el mapa si el seleccionado no tiene posición.
- **Fallos:** sin respuesta del proveedor de teselas, el mapa avisa «Cartografía no disponible» y sigue mostrando las posiciones sobre un fondo liso. Sin WebGL2, el mapa avisa y el resto del centro de mando funciona igual.
- **Atribución obligatoria** (OpenFreeMap, OpenMapTiles y OpenStreetMap) siempre visible, aunque falle el estilo. Los textos de los controles de MapLibre están traducidos.
- **Formulario:** latitud y longitud como texto (coma o punto decimal), validadas como en el backend. «Elegir en el mapa» abre un diálogo donde un clic coloca el punto (se puede arrastrar); los campos siguen siendo la fuente de verdad. La ficha muestra un minimapa de solo lectura o «Sin coordenadas».
- **Privacidad:** al proveedor del mapa base solo se le piden estilo, teselas, fuentes y sprites; los marcadores se dibujan en el navegador.
- **Bases de los recursos asignados (Fase 4):** con un incidente seleccionado, el mapa dibuja solo las bases de sus recursos asignados (`ResourceMarker`, forma distinta a la del incidente; varios recursos con la misma base, un solo marcador «+N»). Sin líneas base → incidente (no hay rutas) y sin capa global de bases. «Ajustar a incidentes» incluye las bases visibles.

### 10.8 i18n

- **Un único idioma** (español) en un único fichero, `src/i18n/locales/es.json`. Ningún texto visible está escrito directamente en los componentes.
- **Claves tipadas:** `t("clave.inexistente")` es un error de compilación.
- **Códigos de la API:** estados, prioridades, tipos, categorías, riesgos, tipos de evento y errores llegan como códigos y se traducen en el frontend. Los códigos de catálogo (que viven en la base de datos) pasan por `lib/code-label.ts`: si llega uno sin traducción, se muestra el propio código en lugar de romper la pantalla.
- **`es.json` se importa por bloques** en `i18n/config.ts`, para que Vite pueda eliminar del bundle de producción el bloque `designSystem`. Un test comprueba que en desarrollo se cargan todos los bloques.

---

## 11. Docker y entorno de desarrollo

| Servicio | Imagen | Puerto en el host | Notas |
|---|---|---|---|
| `db` | `postgis/postgis:18-3.6` | `DB_HOST_PORT` (5433) | Volumen `db-data` en `/var/lib/postgresql` (estructura de PostgreSQL 18). Healthcheck con `pg_isready` por TCP |
| `backend` | `python:3.13-slim` + uv 0.12.23 | `BACKEND_HOST_PORT` (8000) | El entrypoint aplica migraciones y, solo en `development`, el seed. uvicorn `--reload`. Healthcheck en `/api/v1/health` |
| `frontend` | `node:24-slim` + pnpm 12.9.1 | `FRONTEND_HOST_PORT` (5173) | Servidor de desarrollo de Vite; redirige `/api` a `http://backend:8000` |

- **Orden de arranque:** `backend` espera a que `db` esté sano, y `frontend` espera a que `backend` lo esté.
- **Código fuente:** no se monta. `docker compose up --watch` lo sincroniza y Compose reconstruye la imagen si cambian los ficheros de dependencias. Sin `--watch`, hay que reconstruir (`docker compose up -d --build backend frontend`) para ver los cambios; una migración nueva se aplica al arrancar el backend reconstruido.
- **`VITE_MAP_STYLE_URL`:** Compose la pasa al frontend desde `.env` (vacía = OpenFreeMap `dark`).
- **Imágenes solo de desarrollo:** incluyen las dependencias de desarrollo y se ejecutan como root (deuda registrada en `CLAUDE.md` §2.5).
- **Fin de línea:** `.gitattributes` fuerza LF, para que el entrypoint funcione en Linux aunque se clone en Windows.

---

## 12. Calidad y pruebas

| | Herramientas | Qué cubren |
|---|---|---|
| Backend (425 tests) | pytest, ruff, mypy (estricto) | **Fase 1:** configuración, redacción de logs, errores, seguridad (Argon2, JWT), permisos, metadatos de modelos (sin columnas geográficas, fechas con zona), health, login, `/me`, refresh y reutilización, logout, 403 por rol y protección por defecto. **Fase 2:** reglas puras (transiciones, `allowed_transitions`, `details`, recursos), modelos y trigger de solo inserción, eventos en la misma transacción, API de incidentes y recursos (permisos, filtros, orden, paginación, 409, ediciones sin cambios, notas en cerrados, padre/hijo), KPIs del dashboard y seed (marcado, coherencia del historial, idempotencia, no deshace cambios, no consume códigos). **Fase 3:** reglas geográficas puras (rangos, pares, área de la demo, `bbox`), migración con datos (traslado, downgrade y negativa a deshacer `location_changed`) sobre una base de datos propia, PostGIS (tipo, SRID, índice GiST, 1:1), coordenadas en la API (redondeo, `NaN`, códigos de error), `location_changed` y `version`, filtro `has_coordinates`, `GET /incidents/map` (filtros, `bbox`, orden GeoJSON, truncado, 401/403), 422 sin `input`, **coordenadas fuera de los logs** y seed con coordenadas. **Fase 4:** ETA (Haversine, sinuosidad, redondeo, sin coordenadas), reglas de asignación y transiciones automáticas, migraciones con datos y negativa a deshacer asignaciones, API de asignaciones (efectos, errores, varios recursos, llegada, retirada con cada motivo, reasignación atómica, cierre con retirada, bloqueos, permisos, candidatos por ETA sin preselección, ETA guardada que no cambia), **concurrencia real** (dos asignaciones simultáneas: una gana; cierre y reasignación simultáneos terminan de forma coherente y sin interbloqueos; un interbloqueo real de PostgreSQL se traduce a `409 concurrent_update`), índice único parcial, coordenadas de bases fuera de los logs y seed coherente |
| Frontend (108 tests) | Vitest, Testing Library, ESLint, `tsc` | Cliente API, carga de i18n, lógica pura de filtros y formularios, y flujos completos contra un backend falso en memoria que imita el contrato real: login, rutas y navegación por rol, listados con filtros en la URL, detalle e historial, cambios de estado con confirmación, 409 con recarga, edición, notas, altas con validación, desactivación, centro de mando (KPIs, selección, resumen de recursos) y «Volver» con filtros. **Fase 3**, con un doble de `maplibre-gl` (jsdom no tiene WebGL): marcadores, selección mapa ↔ lista ↔ panel, centrado con y sin movimiento reducido, filtros compartidos, encuadre, incidentes sin coordenadas, fallo del mapa base y sin WebGL2, filtro del listado, minimapa, «Elegir en el mapa», validación de coordenadas e historial de `location_changed`. **Fase 4:** candidatos por ETA sin preselección, asignación, retirada con motivo obligatorio, llegada del operador, reasignación confirmada, cierre que enumera los recursos, ficha de recurso asignado bloqueada, panel lateral, indicador y bases (agrupadas) en el mapa, y aviso de `concurrent_update`. **Rediseño:** acciones de estado y de recursos en el panel lateral (con los permisos del operador), plegado de columnas con persistencia y reapertura al seleccionar, recentrado al redimensionar el mapa y barra lateral plegada sin perder los nombres accesibles |

- Los tests del backend usan una base de datos propia (`<POSTGRES_DB>_test`), recreada y migrada desde cero en cada ejecución; cada test corre en una transacción que se deshace. Los del frontend no necesitan backend.
- **Verificación de extremo a extremo** (manual, no versionada): Edge en modo headless controlado por CDP contra el stack de Docker con el seed. Se hace **en solo lectura** sobre la base de desarrollo, porque el historial es de solo inserción y cada escritura consumiría códigos `INC-`; las escrituras están cubiertas por los tests.

---

## 13. Decisiones principales

| Decisión | Motivo |
|---|---|
| Refresh token opaco en cookie httpOnly y access token en memoria | El token de larga duración no queda expuesto a JavaScript (XSS), y el de corta duración no persiste en el navegador |
| Tabla `refresh_tokens` con rotación por familias y margen de 10 s | Cerrar una sesión concreta, detectar la reutilización de un token robado y tolerar dos pestañas que refrescan a la vez |
| Permisos en código; roles en base de datos | Mapa de autorización revisable y versionado, sin depender de datos editables |
| Errores como códigos (`{"detail": "<código>"}`) | El backend no conoce el idioma; el frontend traduce |
| Catálogos de tipos en la migración | Son datos de referencia del sistema, no de demostración |
| Estados y prioridades fijos en código; tipos en base de datos | Flujo uniforme para todos los tipos; catálogo ampliable sin desplegar código |
| `IncidentEvent` en la misma transacción y con trigger de solo inserción | El historial nunca se desincroniza ni se reescribe |
| Bloqueo optimista con `version` y 409, sin «gana el último» | Ningún cambio ajeno se sobrescribe en silencio |
| `allowed_transitions` en la API | El frontend no duplica la máquina de estados |
| Sin `DELETE`: cancelar incidentes y desactivar recursos | Se conserva la trazabilidad |
| Seed con UUIDv5 que solo crea lo que falta | Idempotente y respetuoso con los cambios hechos durante una demo |
| Dashboard como instantánea con su hora, sin sondeo | No simular tiempo real antes de tener WebSockets (Fase 5) |
| Estado de la interfaz en la URL | Pantallas reproducibles y compartibles; «Volver» conserva el contexto |
| La interfaz se adapta a los permisos existentes | Por ejemplo, el filtro de organización se oculta al operador en lugar de ampliar su permiso |
| Proxy de Vite para `/api` | Mismo origen: la cookie de refresh funciona sin CORS con credenciales |
| uv (backend) y pnpm (frontend) | Instalaciones reproducibles con lockfile |
| shadcn/ui sobre Base UI, con `textarea` y `native-select` nativos | Accesibilidad y sencillez, sin dependencias nuevas |
| TypeScript 6.0 y no 7 | `typescript-eslint` todavía no admite TypeScript 7 |
| `docker compose watch` en lugar de volúmenes montados | En Windows, los cambios en volúmenes montados no siempre se detectan, y montar `node_modules` o `.venv` deja dependencias antiguas |
| Base de datos publicada en el 5433 | Evita el conflicto con un PostgreSQL local en el 5432 |
| `Location` 1:1 con el incidente, sin ubicaciones compartidas | Corregir un punto nunca mueve otro incidente ni complica el bloqueo optimista |
| `geometry(Point, 4326)` y no `geography` | No hay cálculos de distancia en la Fase 3 |
| Lat/lon leídas de `geom`, sin columnas duplicadas | Una sola fuente de verdad |
| Área de la demo como regla de validación | Detecta coordenadas intercambiadas; no es geofencing |
| Evento propio `location_changed` con antes y después | La ubicación es operativamente importante y conserva su trazabilidad |
| GeoJSON desde el backend; el mapa no sustituye al listado | MapLibre lo consume tal cual y la lista conserva su paginación |
| `maplibre-gl` directo y marcadores DOM | Una dependencia menos; marcadores accesibles con iconos de Lucide, sin sprites |
| Marcadores compactos (código al seleccionar y en el tooltip) | A escala regional, los marcadores con código se solapaban |
| Atribución propia, siempre visible | El estilo de OpenFreeMap no declara atribuciones, y deben verse aunque falle |
| 422 de validación sin `input` ni `ctx` | No devolver valores recibidos y no romper la respuesta con `NaN` |
| El sistema ordena candidatos, la persona decide | Ayuda a la decisión sin despacho automático; la IA es de la Fase 8 |
| ETA local (Haversine × 1,4 / velocidad del tipo) y guardada al asignar | Sin APIs externas; el historial no cambia retroactivamente |
| Base del recurso como `Location` 1:1 | Segundo consumidor real con las mismas necesidades (coordenadas, validación, área, selector) |
| Índice único parcial para la asignación activa | La base de datos garantiza la regla incluso con peticiones simultáneas |
| `resources_assigned` solo automático | El estado refleja hechos (hay recursos asignados), no una decisión aparte |
| Retirada automática al cerrar o cancelar | Ningún recurso queda bloqueado en un incidente finalizado |
| Varios eventos de una operación separados 1 µs | El timeline los lee en el orden en que ocurrieron |
| Columnas del centro de mando al lado del mapa, no superpuestas | Al plegarlas, el mapa recupera de verdad el espacio y ningún panel tapa marcadores |
| Plegado de paneles en `localStorage`, no en la URL | Es una comodidad de cada puesto (sala o portátil), no un estado que se comparta; ahí no se guardan tokens ni datos |
| Orden global de bloqueos (incidentes → recursos → asignaciones) | Evita interbloqueos entre cerrar un incidente y reasignar uno de sus recursos a la vez |
| Interbloqueo o fallo de serialización de PostgreSQL → `409 concurrent_update` | Si aun así la base de datos aborta una transacción, no se ha guardado nada: el cliente recarga y decide; sin reintentos automáticos ni 500 genérico |

---

## 14. Deuda técnica conocida

- **Límite de intentos de login:** pendiente para una fase de seguridad (`CLAUDE.md` §2.5).
- **Imágenes Docker de producción:** las actuales son de desarrollo y se ejecutan como root (`CLAUDE.md` §2.5).
- **Recursos sin historial de estados:** solo se guarda el último cambio manual; las asignaciones sí tienen historial. La Fase 5 necesitará un evento de recurso para el tiempo real.
- **Iconos de catálogo:** el frontend importa uno a uno los iconos de Lucide que usan los tipos del catálogo; un tipo nuevo con otro icono mostrará uno genérico hasta añadirlo.
- **Filtros de un solo valor en la interfaz** para estado y prioridad (la API ya admite varios).
- **Prueba de extremo a extremo manual**, fuera del repositorio.
- **Sin diseño móvil:** la interfaz está pensada para escritorio (monitor grande y portátil). Por debajo de 1024 px las columnas del centro de mando se apilan para no romperse, pero no hay un layout móvil (fuera de alcance).
- **Coordenadas del seed elegidas a mano:** se han revisado sobre el mapa por muestreo, no punto a punto.
- **Chunk del mapa grande (~1 MB):** MapLibre se carga en diferido, solo en las pantallas con mapa.

---

## 15. Implementado y pendiente

### Implementado y funcional (Fases 1 a 4 y rediseño del centro de mando)

- **Infraestructura:** monorepo, Docker Compose con `db`, `backend` y `frontend`, `.env.example` documentado.
- **Autenticación y RBAC:** login, refresh con rotación, logout, `/me`, permisos por rol en el backend y navegación y acciones filtradas en el frontend.
- **Incidentes:** catálogo de tipos, alta, consulta, edición, ciclo de vida con transiciones validadas, cierre y cancelación con confirmación, incidente padre de un nivel, `details` validados por tipo, concurrencia con `version`.
- **Historial de incidentes:** `IncidentEvent` de solo inserción, timeline en la interfaz y notas.
- **Recursos:** catálogo de tipos, alta, consulta, edición, estado operativo y desactivación.
- **Centro de mando:** mapa como zona principal, franja de KPIs, columnas plegables con los incidentes activos (con filtros) y con el detalle del incidente seleccionado (acciones de estado, recursos asignados con sus acciones y últimos eventos) y el resumen de recursos, con datos reales.
- **Ubicaciones y mapa:** `Location` con PostGIS (`Point` 4326, índice GiST), coordenadas validadas, `location_changed`, `GET /incidents/map` (GeoJSON y `bbox`), mapa del centro de mando con MapLibre y OpenFreeMap, selección mapa ↔ lista ↔ panel, minimapa en la ficha y selección de posición en el formulario.
- **Asignación de recursos y ETA:** bases de recursos, velocidades por tipo, `ResourceAssignment`, candidatos por ETA estimada (sin preselección), asignar, «en el lugar», retirar con motivo, reasignar, retirada al cerrar, `resources_assigned` automático, eventos en el historial y bases de los asignados en el mapa.
- **Seed simulado de Asturias:** organizaciones, usuarios, recursos (con bases), incidentes (con coordenadas aproximadas), asignaciones e historial, todo marcado como simulado.
- **API REST** documentada en OpenAPI y **frontend funcional** con tipos generados, i18n y sistema de diseño propio.
- **Calidad:** tests, lint, comprobación de tipos y build en backend y frontend.

### Preparado pero NO implementado

| Funcionalidad | Qué existe hoy | Qué falta | Fase |
|---|---|---|---|
| Posiciones actuales de recursos | Base con coordenadas; `eta.origin` preparado | `resource_positions` (diseñada), recursos moviéndose en el mapa | Fase 5 |
| Lógica espacial avanzada | Filtro por rectángulo con índice GiST | Distancias, rutas (OSRM), zonas de cobertura, clustering | Fase posterior |
| Mapa sin conexión | `VITE_MAP_STYLE_URL` configurable | Estilo y teselas locales (PMTiles) | Fase posterior |
| Rutas y ETA por carretera | ETA estimada en línea recta × sinuosidad | Rutas reales (OSRM u otras), tiempo de activación | Fase posterior |
| WebSockets / tiempo real | Carpeta `app/realtime/` vacía; `IncidentEvent` preparado como fuente de eventos | EventBus y WebSocket | Fase 5 |
| Redis | — | Solo si hay varios workers | Fase 5 |
| Simulador | Carpeta `app/simulation/` vacía; columnas `is_simulated` | Generador a través de los servicios, `SIMULATION_ENABLED` | Fase 7 |
| IA | Carpeta `app/ai/` vacía | Proveedor basado en reglas detrás de `AIProvider`; siempre recomienda, nunca decide | Fase 8 |
| Hospitales | — | Entidad `Hospital` | Fase posterior |
| Estadísticas avanzadas y gráficos | Solo los KPIs del resumen | Estadísticas a partir de `IncidentEvent` | Fase posterior |
| Notificaciones y auditoría de seguridad | — | `Notification`, `AuditLog` | Fase posterior |
| Integraciones reales | — | **Ninguna prevista:** el proyecto es un prototipo y nunca se conecta a servicios reales de emergencias | — |
