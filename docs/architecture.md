# Arquitectura de Emergency Command

Estado: **Fase 2** (incidentes, recursos y centro de mando con datos reales). Este documento describe lo que **está implementado**. Lo que pertenece a fases posteriores se indica expresamente como tal, y la [sección 15](#15-implementado-y-pendiente) separa con claridad lo que funciona de lo que solo está preparado.

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
│  PostGIS habilitado, sin uso geográfico hasta la Fase 3        │
└────────────────────────────────────────────────────────────────┘
```

- El navegador **solo habla con el frontend**. Vite redirige `/api` al backend, de modo que la cookie de refresh es del mismo origen y no hacen falta peticiones cross-origin en el uso normal.
- El backend también tiene CORS configurado desde `.env` (orígenes explícitos, nunca `*`), para clientes que llamen a la API directamente.
- La comunicación es **REST con JSON**. No hay WebSockets, Redis ni sondeo periódico de datos operativos (el tiempo real está previsto para la Fase 5).

---

## 2. Backend

### 2.1 Pila

Python 3.13, FastAPI, SQLAlchemy 2 (async) con asyncpg, Alembic, pydantic v2 con pydantic-settings, pwdlib (Argon2) y PyJWT. Las dependencias se gestionan con **uv** (`backend/pyproject.toml` y `uv.lock`). Calidad: ruff, mypy en modo estricto y pytest. La Fase 2 no añadió dependencias.

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
│                     enums, exceptions, incident_rules, incident_details, resource_rules
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
  | `ConflictError` | 409 | `version_conflict`, `resource_code_taken` |
  | `InvalidInputError` | 422 | `invalid_transition`, `invalid_details`, `incident_closed`, `resource_inactive` |
  | otro `DomainError` | 400 | |
  | error no controlado | 500 `internal_error`, sin detalles | |

  Los errores de validación de pydantic (formato de la petición) siguen siendo 422 con el detalle estándar de FastAPI; el frontend los trata como `validation_error`.

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
| `GET /incidents` | `incidents:read` | Listado paginado. Filtros: `status`, `priority` (repetibles), `type`, `active` (por defecto solo activos), `q` (código o título), `parent_id`. Orden: `priority`, `-reported_at`, `reported_at`, `-updated_at` |
| `POST /incidents` | `incidents:create` | Alta. Empieza en `received`; sin prioridad, usa la del tipo |
| `GET /incidents/{id}` | `incidents:read` | Detalle con padre, hijos y `allowed_transitions` |
| `PATCH /incidents/{id}` | `incidents:update` | Edición parcial con `version` obligatoria |
| `POST /incidents/{id}/status` | `incidents:update` (+ `incidents:close` para cerrar o cancelar) | Cambio de estado con `version` y motivo opcional |
| `GET /incidents/{id}/events` | `incidents:read` | Historial del incidente en orden cronológico |
| `POST /incidents/{id}/notes` | `incidents:update` | Nota en el historial (también en incidentes cerrados o cancelados) |
| `GET /resource-types` | `resources:read` | Catálogo de tipos de recurso |
| `GET /resources` | `resources:read` | Listado paginado. Filtros: `status`, `type`, `organization_id`, `municipality`, `active`, `q`. Orden: `code`, `status`, `-status_changed_at` |
| `POST /resources` | `resources:manage` | Alta de un recurso |
| `GET /resources/{id}` | `resources:read` | Ficha del recurso |
| `PATCH /resources/{id}` | `resources:manage` | Edición de la ficha, incluida la (des)activación, con `version` |
| `POST /resources/{id}/status` | `resources:update_status` | Cambio de estado operativo con `version` |
| `GET /dashboard/summary` | `incidents:read` + `resources:read` | KPIs del centro de mando ([sección 7](#7-resumen-del-centro-de-mando)) |

**Protegido por defecto:** `app/api/v1/router.py` registra los endpoints públicos uno a uno y cuelga el resto de un router que exige un access token válido. Un test recorre el esquema OpenAPI y comprueba que cualquier ruta no pública responde 401 sin token.

`/docs` y `/openapi.json` solo existen con `ENVIRONMENT=development`.

### 2.4 Configuración y logging

- `core/config.py` (pydantic-settings) lee las variables de entorno y el `.env` de la raíz. Con `ENVIRONMENT=production` el backend no arranca si la clave JWT o la contraseña de la base de datos conservan los valores de ejemplo, o si la cookie de refresh no es `Secure`.
- `core/logging.py` aplica a todos los handlers (también los de uvicorn) un filtro que tapa contraseñas, `Bearer …`, JWT, tokens y cookies. Además, el motor de SQLAlchemy usa `hide_parameters=True`, y los errores no controlados se registran solo con su tipo, sin el mensaje.

---

## 3. Modelo de datos

Dos migraciones en `backend/alembic/versions/`:

| Migración | Contenido |
|---|---|
| `20261007_2c90a9ee7694` (Fase 1) | `CREATE EXTENSION postgis`; tablas `roles`, `organizations`, `users`, `refresh_tokens`; los tres roles |
| `20261007_48bc2488f9e1` (Fase 2) | Catálogos `incident_types` y `resource_types` con sus datos de referencia; `incidents` con la secuencia `incident_code_seq`; `incident_events` con su trigger de solo inserción; `resources` |

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
municipality        varchar(100)
location_description varchar(255) NULL            resources
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

### 3.3 Detalles comunes

- **Fechas:** todas son `timestamptz` en UTC. `db/base.py` lo impone para cualquier `datetime` y un test lo comprueba. El frontend las muestra en Europe/Madrid.
- **Claves primarias:** UUID, generado en Python (`uuid4`) con valor por defecto en el servidor (`gen_random_uuid()`) para las inserciones en SQL.
- **Enums como `varchar` + `CHECK`**, no como `ENUM` nativo: añadir un valor no exige `ALTER TYPE`.
- **Nombres de restricciones** deterministas (`pk_…`, `uq_…`, `fk_…`, `ck_…`, `ix_…`), para que las migraciones sean estables.
- **Relaciones:** con `lazy="raise"`. En async no hay carga perezosa implícita y los repositorios cargan las relaciones de forma explícita.
- **Datos de referencia en las migraciones:** roles y catálogos de tipos existen en todos los entornos; no son datos de demostración.
- **Sin borrados:** los incidentes se cancelan y los recursos se desactivan (`is_active`). No hay endpoints `DELETE`.
- **Sin geometría:** ninguna columna, índice ni consulta geográfica. La ubicación es solo municipio y una descripción genérica; un test de metadatos falla si aparece una columna `geometry`/`geography`.
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

cancelled: desde received, assessing o in_progress
resources_assigned: existe en el enum, pero no es alcanzable hasta que haya asignaciones
```

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
| `incident_updated` | `fields` (lista de campos modificados) |
| `note_added` | `text` |
| `parent_changed` | `from`, `to` (códigos de incidente o nulo) |

- Cada cambio inserta su evento **en la misma transacción** que el propio cambio: el historial no puede desincronizarse del incidente.
- **Solo inserción**, también en la base de datos: un trigger impide `UPDATE`, `DELETE` y `TRUNCATE`.
- El `payload` lleva códigos y valores; el frontend compone la frase traducida.
- `actor_user_id` nulo significa que el evento lo generó el sistema (por ejemplo, el seed); la interfaz lo muestra como «Sistema».
- **Una edición sin cambios reales no escribe nada:** ni evento ni incremento de `version`.

### 4.6 Concurrencia

- **Bloqueo optimista con `version`:** toda escritura (edición, cambio de estado) envía la `version` que leyó. Si no coincide, responde `409 version_conflict` sin efectos. No existe «gana el último».
- **`SELECT … FOR UPDATE`** sobre la fila al modificarla: dos cambios simultáneos se serializan.
- **Validar antes de modificar:** los servicios hacen todas las consultas de validación (padre, tipo, organización) antes de tocar el objeto, para que un autoflush no emita un `UPDATE` intermedio y `version` suba exactamente una vez por petición.
- **Códigos legibles** (`INC-000123`) de una única secuencia PostgreSQL, compartida por incidentes reales y simulados; `is_simulated` distingue el origen.

---

## 5. Recursos

- **Ficha:** código, nombre, tipo, organización, municipio base, estado, `status_changed_at`, `is_active`, `is_simulated` y `version`. **Sin coordenadas** (Fase 3) y **sin historial** propio: solo se guarda el último cambio de estado.
- **Código inmutable:** se normaliza a mayúsculas y es único (`409 resource_code_taken`).
- **Estados operativos:** `available`, `in_service`, `out_of_service`. Se puede pasar de cualquiera a cualquier otro; repetir el actual es `422 invalid_transition` (`domain/resource_rules.py`).
- **Desactivación:** `is_active = false` por `PATCH`. Un recurso desactivado no cambia de estado (`422 resource_inactive`) hasta que se reactive, pero su ficha sí se puede editar.
- **Tipo y organización nuevos** deben estar activos; un recurso puede seguir asociado a uno que se desactivó después.
- **Bloqueo optimista** con `version`, igual que en incidentes.
- **Sin asignaciones:** el estado `in_service` se cambia a mano. La relación recurso ↔ incidente (`ResourceAssignment`) es de una fase posterior.

---

## 6. Datos simulados y datos reales

- **Ubicación:** los datos de demostración viven **solo** en `backend/seeds/` (`fixtures.py`, `seed.py` y `operational.py`). No hay datos falsos en componentes, servicios ni routers.
- **Contenido:**

  | Datos | Cantidad | Marcado |
  |---|---|---|
  | Organizaciones | 4 (coordinación Asturias, bomberos Oviedo, sanitario Gijón, protección civil Avilés) | `is_simulated`, código `sim-…`, «(simulado)» en el nombre |
  | Usuarios | 3, uno por rol | email del dominio reservado `.test` |
  | Recursos | 18 (11 disponibles, 5 en servicio, 2 fuera de servicio) | `is_simulated`, código `SIM-…`, «(simulado)» en el nombre |
  | Incidentes | 12 en Oviedo, Gijón, Avilés, Siero, Mieres y Aller: todas las prioridades y estados alcanzables, 2 cerrados, 1 cancelado y un temporal con dos incidentes hijos | `is_simulated`, «(simulado)» en el título, ubicación genérica «(ubicación simulada)» |
  | Eventos del historial | 38, coherentes con el estado final de cada incidente | `is_simulated`, actor nulo («Sistema») |

  Ningún teléfono, dirección, indicativo, URL ni nombre corresponde a un servicio real.

- **Solo en desarrollo:** el seed se niega a ejecutarse fuera de `ENVIRONMENT=development`. La contraseña de los usuarios demo sale de `DEMO_USER_PASSWORD`.
- **Idempotente**, con un cerrojo consultivo de PostgreSQL para que dos ejecuciones no se pisen:
  - **usuarios y organizaciones:** crea lo que falta y devuelve lo existente al estado de los fixtures;
  - **recursos e incidentes:** ids fijos derivados de una clave del fixture (UUIDv5); **solo crea lo que falta y nunca modifica lo existente**. El seed no es una herramienta de sincronización ni de restauración: lo que se cambie durante una demo se conserva. Repetirlo no consume números de la secuencia `INC-`.
- **Mismas reglas que la API:** cada historial se valida con `can_transition` y cada `details` con su esquema; un fixture incoherente hace fallar el seed sin escribir nada.
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
  | `incidents:create` | ✅ | ✅ | ❌ |
  | `incidents:update` (editar, cambiar estado, notas) | ✅ | ✅ | ❌ |
  | `incidents:close` (cerrar o cancelar) | ✅ | ✅ | ❌ |
  | `resources:read` | ✅ | ✅ | ✅ |
  | `resources:update_status` | ✅ | ✅ | ✅ |
  | `resources:manage` (alta, edición, desactivación) | ✅ | ❌ | ❌ |
  | `organizations:read` | ✅ | ✅ | ❌ |

- **Comprobación:** con la dependencia `require_permission(Permission.X)` en el router. Cerrar o cancelar se comprueba en el servicio, porque depende del estado de destino. Sin permiso responde `403 {"detail":"permission_denied"}`.
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
- **Calidad:** ESLint (`strictTypeChecked`), Prettier y Vitest con Testing Library.
- **Gestor de paquetes:** pnpm. La Fase 2 no añadió dependencias.

### 10.2 Estructura

```
src/
├─ app/                  router, providers, query client, layout y rutas genéricas
│  ├─ layout/            AppShell, Sidebar (navegación por permisos), TopBar (conexión y reloj)
│  ├─ routes/            ProtectedRoute, RequirePermission, 404, 403, error, carga
│  └─ dev/design-system/ catálogo de desarrollo (solo con import.meta.env.DEV)
├─ components/ui/        componentes de shadcn/ui (código de terceros, cambios mínimos)
├─ components/ops/       sistema de diseño propio (ver 10.6)
├─ features/
│  ├─ auth/              sesión, login, permisos
│  ├─ command-center/    resumen del dashboard y paneles del centro de mando
│  ├─ incidents/         api, hooks, types, filters, form, presentation, components
│  ├─ resources/         api, hooks, types, filters, form, presentation, components
│  ├─ organizations/     listado de organizaciones
│  └─ system/            health
├─ lib/                  api-client, query-keys, query-string, navigation, code-label,
│                        form-a11y, format, utils
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
| `/` | sesión | **Centro de mando:** KPIs, incidentes activos con filtros, panel lateral del incidente seleccionado (resumen y últimos 5 eventos), resumen de recursos por estado y **zona del mapa reservada** (vacía) |
| `/incidents` | `incidents:read` | Listado con filtros, orden y paginación |
| `/incidents/new` | `incidents:create` | Alta con validación y sección fija de `details` según el tipo |
| `/incidents/:id` | `incidents:read` | Detalle, acciones de estado, edición, padre/hijos, historial y notas |
| `/resources` | `resources:read` | Listado con filtros, orden y paginación |
| `/resources/new` | `resources:manage` | Alta de recurso |
| `/resources/:id` | `resources:read` | Ficha, cambio de estado, edición y desactivación |
| `/organizations` | `organizations:read` | Listado de organizaciones |
| `/dev/design-system` | solo desarrollo | Catálogo del sistema de diseño; no existe en producción |

Las páginas se cargan bajo demanda (`lazy`), así que el bundle inicial solo contiene el router, la sesión y el layout.

**Comportamientos comunes:**

- **Datos solo de la API.** Ninguna pantalla contiene datos de ejemplo; todo llega del backend y se marca «Simulado» cuando `is_simulated` es verdadero.
- **Estados** de carga, vacío, vacío por filtros y error con «Reintentar» en todos los paneles (`Panel`).
- **Estado en la URL:** filtros, orden, página y, en el centro de mando, el incidente seleccionado (`/?incident=…&priority=…`). Se pueden compartir y sobreviven a una recarga.
- **«Volver»** regresa a la pantalla de origen con sus filtros, página o selección (`lib/navigation.ts`).
- **Acciones según el backend:** los cambios de estado de un incidente salen de `allowed_transitions`; la interfaz no duplica el flujo.
- **Confirmaciones:** cerrar, cancelar (con motivo opcional) y desactivar piden confirmación, con el foco inicial en la opción de no hacer nada. Los cambios operativos frecuentes (por ejemplo, el estado de un recurso) no.
- **Conflictos:** un `409 version_conflict` muestra «El incidente/recurso ha cambiado» con «Recargar». Recargar descarta los cambios locales y muestra la versión actual; nunca se sobrescribe un cambio ajeno.
- **Sin cambios, sin llamada:** guardar una edición sin cambios no llama a la API.
- **Refresco:** tras cada escritura se invalidan listados, detalle y KPIs. No hay sondeo periódico ni tiempo real.

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

**Componentes de `components/ops/`:** `Panel` (estados de carga, vacío y error), `PriorityBadge`, `StatusPill`, `SimulatedPill`, `KpiTile`, `ConfirmDialog` (admite contenido adicional, como un motivo), `MutationErrorAlert` (errores de escritura y 409), `FilterSelect`, `Pagination`, `BackLink`, `DetailItem`/`DateTimeText` y `FormField`.

**Catálogo:** `/dev/design-system` muestra los tokens y los componentes base en sus estados. Vite elimina esa ruta, su código y sus textos del build de producción.

### 10.7 i18n

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
- **Código fuente:** no se monta. `docker compose up --watch` lo sincroniza y Compose reconstruye la imagen si cambian los ficheros de dependencias. Sin `--watch`, hay que reconstruir para ver los cambios.
- **Imágenes solo de desarrollo:** incluyen las dependencias de desarrollo y se ejecutan como root (deuda registrada en `CLAUDE.md` §2.5).
- **Fin de línea:** `.gitattributes` fuerza LF, para que el entrypoint funcione en Linux aunque se clone en Windows.

---

## 12. Calidad y pruebas

| | Herramientas | Qué cubren |
|---|---|---|
| Backend (283 tests) | pytest, ruff, mypy (estricto) | **Fase 1:** configuración, redacción de logs, errores, seguridad (Argon2, JWT), permisos, metadatos de modelos (sin columnas geográficas, fechas con zona), health, login, `/me`, refresh y reutilización, logout, 403 por rol y protección por defecto. **Fase 2:** reglas puras (transiciones, `allowed_transitions`, `details`, recursos), modelos y trigger de solo inserción, eventos en la misma transacción, API de incidentes y recursos (permisos, filtros, orden, paginación, 409, ediciones sin cambios, notas en cerrados, padre/hijo), KPIs del dashboard y seed (marcado, coherencia del historial, idempotencia, no deshace cambios, no consume códigos) |
| Frontend (75 tests) | Vitest, Testing Library, ESLint, `tsc` | Cliente API, carga de i18n, lógica pura de filtros y formularios, y flujos completos contra un backend falso en memoria que imita el contrato real: login, rutas y navegación por rol, listados con filtros en la URL, detalle e historial, cambios de estado con confirmación, 409 con recarga, edición, notas, altas con validación, desactivación, centro de mando (KPIs, selección, resumen de recursos) y «Volver» con filtros |

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

---

## 14. Deuda técnica conocida

- **Límite de intentos de login:** pendiente para una fase de seguridad (`CLAUDE.md` §2.5).
- **Imágenes Docker de producción:** las actuales son de desarrollo y se ejecutan como root (`CLAUDE.md` §2.5).
- **Recursos sin historial:** solo se guarda el último cambio de estado; el historial completo llegará con las asignaciones.
- **Iconos de catálogo:** el frontend importa uno a uno los iconos de Lucide que usan los tipos del catálogo; un tipo nuevo con otro icono mostrará uno genérico hasta añadirlo.
- **Filtros de un solo valor en la interfaz** para estado y prioridad (la API ya admite varios).
- **Prueba de extremo a extremo manual**, fuera del repositorio.

---

## 15. Implementado y pendiente

### Implementado y funcional (Fases 1 y 2)

- **Infraestructura:** monorepo, Docker Compose con `db`, `backend` y `frontend`, `.env.example` documentado.
- **Autenticación y RBAC:** login, refresh con rotación, logout, `/me`, permisos por rol en el backend y navegación y acciones filtradas en el frontend.
- **Incidentes:** catálogo de tipos, alta, consulta, edición, ciclo de vida con transiciones validadas, cierre y cancelación con confirmación, incidente padre de un nivel, `details` validados por tipo, concurrencia con `version`.
- **Historial de incidentes:** `IncidentEvent` de solo inserción, timeline en la interfaz y notas.
- **Recursos:** catálogo de tipos, alta, consulta, edición, estado operativo y desactivación.
- **Centro de mando:** KPIs, incidentes activos con filtros, panel lateral del incidente seleccionado y resumen de recursos, con datos reales.
- **Seed simulado de Asturias:** organizaciones, usuarios, recursos, incidentes e historial, todo marcado como simulado.
- **API REST** documentada en OpenAPI y **frontend funcional** con tipos generados, i18n y sistema de diseño propio.
- **Calidad:** tests, lint, comprobación de tipos y build en backend y frontend.

### Preparado pero NO implementado

| Funcionalidad | Qué existe hoy | Qué falta | Fase |
|---|---|---|---|
| Mapa (MapLibre GL JS + OpenFreeMap) | Zona reservada y vacía en el centro de mando | Todo: no hay librería de mapas ni capas | Fase 3 o posterior |
| PostGIS espacial | Extensión habilitada en la base de datos | Columnas geométricas, `Location`, índices y consultas espaciales | Fase 3 |
| Asignación de recursos | Estado `resources_assigned` en el enum (inalcanzable) y estado `in_service` manual | `ResourceAssignment`, eventos de asignación e historial de recursos | Fase posterior |
| ETA | — | Cálculo estimado por distancia y tipo | Fase posterior |
| WebSockets / tiempo real | Carpeta `app/realtime/` vacía; `IncidentEvent` preparado como fuente de eventos | EventBus y WebSocket | Fase 5 |
| Redis | — | Solo si hay varios workers | Fase 5 |
| Simulador | Carpeta `app/simulation/` vacía; columnas `is_simulated` | Generador a través de los servicios, `SIMULATION_ENABLED` | Fase 7 |
| IA | Carpeta `app/ai/` vacía | Proveedor basado en reglas detrás de `AIProvider`; siempre recomienda, nunca decide | Fase 8 |
| Hospitales | — | Entidad `Hospital` | Fase posterior |
| Estadísticas avanzadas y gráficos | Solo los KPIs del resumen | Estadísticas a partir de `IncidentEvent` | Fase posterior |
| Notificaciones y auditoría de seguridad | — | `Notification`, `AuditLog` | Fase posterior |
| Integraciones reales | — | **Ninguna prevista:** el proyecto es un prototipo y nunca se conecta a servicios reales de emergencias | — |
