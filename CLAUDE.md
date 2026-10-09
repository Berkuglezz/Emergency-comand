# CLAUDE.md — Emergency Command

Este fichero define las reglas persistentes del proyecto. Léelo completo al inicio de cada sesión. Si una instrucción de una tarea contradice este fichero, detente y pregunta antes de actuar.

---

## 1. Qué es este proyecto

Emergency Command es un **prototipo demostrable** de plataforma de coordinación de emergencias: incidentes, recursos, mapa, timeline y tiempo real desde una única interfaz de centro de operaciones.

- **No es un sistema real.** Nunca se conecta al 112, a servicios públicos ni a ninguna fuente real de emergencias.
- Debe sentirse como un centro de mando profesional, no como un CRUD universitario.
- Debe poder ejecutarse localmente con Docker Compose y abrirse con datos de demostración.

---

## 2. Alcance por fases

| Fase | Estado |
|---|---|
| Fase 1: base técnica | **Completada** (ver §2.1 y §11.1) |
| Fase 2: incidentes, recursos y dashboard funcional | **Completada** (ver §2.3 y §11.2) |
| Fase 3: geolocalización (PostGIS + `Location`) y mapa funcional | **Completada** (ver §2.6 y §11.3) |
| Fase 4: asignación de recursos y ETA | **Completada** (ver §2.8 y §11.4) |
| Etapa de rediseño del centro de mando (visual, sin funcionalidad nueva) | **Completada** (ver §2.10.1) |
| Etapa de roles, permisos y ámbito organizativo | **Completada** (ver §2.11 y §11.5) |

Trabaja **solo** en el alcance de la fase autorizada. Todo lo demás está fuera de alcance aunque parezca útil o rápido de añadir.

### 2.1 Incluido en Fase 1 (completada)

**Infraestructura**
- Monorepo con `backend/`, `frontend/`, `docs/`.
- `docker-compose.yml` con servicios `db`, `backend`, `frontend`.
- La imagen de base de datos es `postgis/postgis` desde el inicio, para no cambiar de imagen más adelante. La extensión puede habilitarse en la migración inicial, pero en Fase 1 **no** se usa PostGIS en la lógica de negocio: no se crean columnas geométricas, índices espaciales, consultas espaciales ni ninguna funcionalidad geográfica. Todo eso empieza en Fase 3.
- `.env.example` documentado. Ningún secreto en el código.

**Backend**
- Estructura por capas completa (ver §4), aunque algunas carpetas queden vacías.
- Configuración con `pydantic-settings`.
- SQLAlchemy 2 async + asyncpg.
- Alembic con la migración inicial, que contiene solo `roles`, `organizations` y `users`.
- Autenticación:
  - Endpoints: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
  - Contraseñas con Argon2 (`pwdlib[argon2]`).
  - Access token JWT de corta duración, devuelto en el cuerpo de la respuesta.
  - Refresh token en cookie `httpOnly`, `Secure` (configurable en desarrollo) y `SameSite=Lax`.
- RBAC:
  - Roles `admin`, `coordinator`, `operator`.
  - Mapa rol → permisos definido en código (`app/core/permissions.py`).
  - Dependencia `require_permission("...")`.
- CORS configurado desde `.env`.
- Endpoint `GET /api/v1/health`.
- Seed de demostración en `backend/seeds/`, con tres usuarios (uno por rol) y organizaciones de ejemplo.
- Tests: autenticación correcta e incorrecta, refresh, acceso denegado por rol, health.

**Frontend**
- Base: Vite + React + TypeScript (modo estricto).
- Estilos: Tailwind CSS v4 (`@tailwindcss/vite`) y shadcn/ui.
- Iconos: lucide-react.
- Navegación y datos: React Router y TanStack Query.
- i18n: react-i18next con un único fichero `es.json`. Ningún texto visible queda hardcodeado en componentes.
- Tokens de diseño en `src/styles/tokens.css` (ver §7).
- Componentes base del sistema: `Panel`, `PriorityBadge`, `StatusPill`, `KpiTile`, `ConfirmDialog`, botones, tabla, campos de formulario y alertas.
- Ruta `/dev/design-system`:
  - Solo existe en desarrollo. Se registra únicamente cuando `import.meta.env.DEV` es verdadero, de modo que no se incluye en el build de producción.
  - No aparece en la navegación de la aplicación.
  - Es solo un catálogo de los componentes reales de `components/ops/` y `components/ui/`, importados tal cual. No contiene lógica, formularios funcionales, llamadas a la API ni componentes propios. No debe convertirse en una segunda aplicación.
  - Muestra cada componente en todas sus variantes y estados (loading, empty, error, deshabilitado, foco), la paleta de tokens, la escala tipográfica y los iconos de estado.
  - Sirve para revisar contraste, foco de teclado y comportamiento responsive.
  - Los valores de ejemplo que use son estáticos, viven en un único fichero dentro de la propia ruta y no se reutilizan en ningún otro sitio.
- Layout del centro de mando:
  - Barra lateral.
  - Barra superior con reloj y estado de conexión.
  - Zonas reservadas para mapa, lista y panel lateral, con estados vacíos. Sin datos falsos.
- Pantalla de login.
- Rutas protegidas y navegación filtrada por rol.
- Cliente API:
  - Access token guardado en memoria.
  - Refresh automático ante un 401.
  - Cierre de sesión si el refresh falla.
- Tests básicos de login y de rutas protegidas.

**Documentación**
- `README.md` con instalación, ejecución con Docker y ejecución sin Docker.
- `docs/architecture.md`.

### 2.2 Fuera de alcance en Fase 1 (no implementar)

Incidentes, recursos, mapa/MapLibre, PostGIS en modelos o consultas, asignaciones, timeline, WebSockets, Redis, hospitales, estadísticas, historial, simulador, IA, notificaciones y gráficos.

Si una tarea de Fase 1 parece requerir algo de esta lista, **pregunta antes**.

### 2.3 Fase 2: incidentes, recursos y dashboard funcional (completada)

**Incidentes**
- Modelo `Incident`, catálogo `IncidentType` e `IncidentEvent` como historial/timeline (solo inserción, ver §5).
- Estados y prioridades (enums fijos de §5), definidos en el backend y expuestos por OpenAPI.
- API de incidentes (alta, consulta, edición y cambios de estado).
- Validación de `details` según el tipo de incidente (§5).
- `parent_incident_id` (§5) e `is_simulated`.
- Control de concurrencia/versionado de las modificaciones.
- Lista de incidentes activos, detalle de incidente, filtros y ordenación básicos y timeline del incidente.

**Recursos**
- Modelo `Resource` asociado a organizaciones, con tipos y estados de recurso.
- API de recursos, lista y detalle de recursos.

**Centro de mando**
- Sustituir los estados vacíos actuales por datos reales de la API/BD: lista de incidentes activos, resumen de recursos y KPIs con datos reales disponibles.
- Estados loading/empty/error y filtros básicos.
- La zona del mapa sigue reservada (sin mapa funcional), preparada para conectarlo después.

**Datos**
- Seed de incidentes y recursos simulados de Asturias, todo marcado como simulado.
- Nada de teléfonos, nombres, ubicaciones operativas ni integraciones reales que puedan confundirse con un sistema de emergencias real.

**API y frontend**
- Se mantienen el cliente API, i18n, el sistema de diseño y el RBAC existentes.
- Los tipos del frontend se generan con `pnpm gen:api`. No se duplican a mano tipos que pueda generar OpenAPI.
- `PriorityCode` (definido a mano en Fase 1 en `components/ops/priority.ts`) se ha sustituido por el tipo generado de `Incident.priority`. Una sola fuente de verdad.

### 2.4 Fuera de alcance en Fase 2 (no implementar)

Mapa funcional, MapLibre/OpenFreeMap, PostGIS en modelos o consultas, asignación de recursos, ETA, recomendaciones de recursos, WebSockets, Redis, simulador, IA/Ollama, hospitales, estadísticas avanzadas e integraciones reales con servicios de emergencia.

Si una tarea de Fase 2 parece requerir algo de esta lista, **pregunta antes**.

### 2.5 Deuda técnica registrada (para fases posteriores)

- Límite de intentos de login: pendiente para una fase de seguridad, salvo que en Fase 2 surja una razón concreta.
- Imágenes Docker de producción: se abordarán junto con despliegue y seguridad. Las actuales son de desarrollo.
- Registrada al cerrar Fase 2 (no bloquea; detalle en `docs/architecture.md` §14):
  - Recursos sin historial: solo se guarda el último cambio de estado; el historial completo llegará con las asignaciones.
  - Iconos del catálogo de tipos importados uno a uno desde Lucide; un icono nuevo muestra uno genérico hasta añadirlo.
  - Filtros de un solo valor en la interfaz para estado y prioridad (la API ya admite varios).
  - Prueba de extremo a extremo manual, fuera del repositorio.

### 2.6 Fase 3: geolocalización y mapa funcional (completada)

Propuesta técnica aprobada y fase cerrada el 2026-10-08. Se implementó por etapas:

| Etapa | Contenido |
|---|---|
| 3.1 Datos y modelo | `geoalchemy2`, `Location`, migración con traslado de datos, índice GiST, `location` anidada **solo textual**. Sin coordenadas en la API ni UX de ubicación |
| 3.2 API de ubicación | Coordenadas en la API, validación, `location_changed`, filtro `has_coordinates`, `GET /incidents/map` |
| 3.3 Seed | Coordenadas simuladas, incidentes sin coordenadas a propósito; reinicio de la BD de desarrollo |
| 3.4 Mapa base | MapLibre + OpenFreeMap `dark`, atribución, encuadre de Asturias, fallback sin teselas, nueva disposición |
| 3.5 Marcadores e interacción | Marcadores, leyenda, mapa ↔ lista ↔ panel por URL, filtros compartidos |
| 3.6 Formularios y ficha | Coordenadas en alta/edición, «Elegir en el mapa», minimapa en la ficha, timeline de `location_changed` |
| 3.7 Documentación y cierre | README, `docs/architecture.md`, accesibilidad, clon limpio, resumen §12 |

**Modelo**
- `Location` 1:1 con `Incident` (`incidents.location_id` `NOT NULL UNIQUE` → `locations.id`). Solo la usa `Incident`: nada de `Place`, repositorios genéricos ni abstracciones para otras entidades.
- `locations`: `municipality` (obligatorio), `description`, `geom geometry(Point, 4326)` nullable (NULL = sin coordenadas), índice GiST.
- Latitud/longitud no se guardan en columnas propias: se leen de `geom`. Recursos siguen con `municipality` textual.
- `geoalchemy2` solo para integrar `Geometry` con SQLAlchemy/Alembic; sin Shapely.

**API**
- `location` anidada (`LocationInput` / `LocationResponse`) sustituye a `municipality` y `location_description`, sin capa de compatibilidad. En edición, `location` se envía completa.
- Coordenadas WGS84 en grados decimales: rangos, ambas o ninguna, sin `NaN`/infinitos, 6 decimales. Fuera del rectángulo de Asturias → 422 `location_out_of_area` (protección de la demo, no geofencing).
- Cambiar la ubicación incrementa `version` una vez y registra `location_changed` con el antes y el después.
- `GET /api/v1/incidents/map`: `FeatureCollection` GeoJSON con datos mínimos, filtros de estado/prioridad, `bbox` opcional, `unlocated_total`, tope de 1.000 con `truncated`. **No sustituye a `GET /incidents`**, que sigue alimentando la lista.

**Frontend**
- `maplibre-gl` directo (sin `react-map-gl`), carga diferida, estilo OpenFreeMap `dark` configurable con `VITE_MAP_STYLE_URL`, atribución siempre visible, fallback sin mapa base.
- Disposición de la Fase 3: mapa en ~55 % de la zona principal y lista debajo. **Sustituida** por la del rediseño del centro de mando (§2.10.1).
- Marcadores DOM accesibles y compactos: color + icono por prioridad, borde por estado; el código se muestra al seleccionar y en el tooltip, y el nombre accesible incluye código, prioridad, estado y simulado (cambio tras la revisión visual: con el código siempre visible se solapaban a escala regional). Sin popup en el centro de mando (el detalle está en el panel lateral).
- Selección y filtros en la URL, compartidos por mapa, lista y panel. Incidentes sin coordenadas: aviso con recuento y filtro, nunca ocultos.

**Datos y seguridad**
- Seed: coordenadas redondeadas a 3 decimales en zonas públicas genéricas, nunca sobre instalaciones reales de emergencias; se mantiene la regla «crea lo que falta, no pisa lo existente» y se reinicia la BD de desarrollo.
- Las coordenadas pueden estar en `IncidentEvent.payload` (historial protegido por `incidents:read`), pero **nunca en logs de aplicación, mensajes de excepción ni trazas**.
- Al proveedor de teselas solo se le piden teselas: nunca se le envían coordenadas ni datos de incidentes. Sin geocodificación.

**Dependencias aprobadas:** `geoalchemy2` 0.20.0 y `maplibre-gl` 6.13.0.

### 2.7 Fuera de alcance en Fase 3 (no implementar)

GPS de recursos, recursos en el mapa, asignaciones, rutas, ETA, OSRM, distancias, geocodificación, geofencing, zonas de cobertura, clustering, consultas espaciales distintas del filtro por rectángulo, WebSockets, polling, Redis, IA/Ollama, hospitales, simulador, estadísticas avanzadas, PMTiles/offline e integraciones reales con servicios de emergencia.

Si una tarea de Fase 3 parece requerir algo de esta lista, **pregunta antes**.

### 2.8 Fase 4: asignación de recursos y ETA (completada)

Especificación aprobada el 2026-10-08 y fase cerrada el 2026-10-09. **Principio rector: el sistema informa → la persona responsable decide → el sistema ejecuta.** El sistema ordena candidatos y marca tipos sugeridos, pero nunca preselecciona ni asigna automáticamente (eso no es IA ni recomendación automática; la IA es Fase 8).

Se implementó por etapas, cada una verificada y aprobada antes de seguir:

| Etapa | Contenido |
|---|---|
| 4.1 Bases y velocidades | Base del recurso como `Location` 1:1, `resource_types.average_speed_kmh`, migraciones de datos, bases con coordenadas en el seed. Sin asignaciones |
| 4.2 Dominio | Cálculo de ETA (`domain/eta.py`), reglas de asignación y transiciones nuevas, todo puro y testeado |
| 4.3 Asignaciones en backend | `ResourceAssignment`, migraciones, servicio, `IncidentEvent` nuevos, API y permisos |
| 4.4 Frontend de recursos | Base en ficha y formulario, asignación actual, cambio de estado bloqueado si está asignado |
| 4.5 Frontend del incidente | Panel de asignados, diálogo «Asignar recurso», llegada, retirada, reasignación, cierre con recursos y timeline |
| 4.6 Mapa | Bases de los recursos asignados al incidente seleccionado |
| 4.7 Cierre | Seed de asignaciones, documentación, clon limpio y resumen §12 |

**Posición del recurso**
- En la Fase 4 solo existe la **base** del recurso (dónde está destinado). La posición actual/GPS es Fase 5.
- La base reutiliza `Location` 1:1: `resources.base_location_id NOT NULL UNIQUE` → `locations.id`. Se revisa la decisión de la Fase 3 de no generalizar `Location` porque ahora hay un segundo consumidor real con las mismas necesidades (coordenadas, validación, área de Asturias, selector en el mapa, API). Las filas nunca se comparten entre recursos ni con incidentes. `resources.municipality` se traslada a la base y desaparece.
- Diseño previsto para la Fase 5 (no se implementa ahora): `resource_positions` de solo inserción (`resource_id`, `geom` Point 4326, `recorded_at`, `source` manual|simulated|gps, `is_simulated`). La ETA lleva `origin` (`"base"` en la Fase 4; `"last_position"` en la Fase 5) para no cambiar el contrato.

**ETA**
- Cálculo local y determinista en el dominio, sin APIs externas ni rutas por carretera: `minutos = ceil(haversine_km × 1.4 / velocidad_media_del_tipo × 60)`.
- Factor de sinuosidad global 1.4. Velocidades medias por tipo (km/h) en el catálogo: autobomba 50, vehículo de rescate 55, ambulancia básica 60, ambulancia avanzada 65, vehículo de mando 60, unidad de protección civil 50, apoyo logístico 45. Sin tiempo de activación.
- Resultado: `{minutes, distance_km (1 decimal), origin: "base"}`, o `null` con motivo (`incident_without_coordinates`, `resource_without_position`).
- **La estimación se guarda en la asignación en el momento de asignar** (`eta_minutes`, `eta_distance_km`, `eta_origin`): cambiar después una base o una velocidad nunca altera el historial.
- Siempre se presenta como «estimado» (p. ej. «≈ 12 min · 8,4 km (estimado)», «llegada estimada hh:mm»), con icono y texto; nunca como hora exacta.

**`ResourceAssignment`**
- Tabla `resource_assignments`: `incident_id`, `resource_id`, `assigned_at`, `assigned_by_id`, `arrived_at`, `released_at`, `released_by_id`, `release_reason`, `eta_minutes`, `eta_distance_km`, `eta_origin`, `is_simulated`, `created_at`, `updated_at`. Activa = `released_at IS NULL`. Nunca se borra.
- Índice único parcial `(resource_id) WHERE released_at IS NULL`: **un recurso solo puede tener una asignación activa**. Un incidente puede tener **varios recursos**.
- **Asignar:** incidente activo (con su `version`), recurso activo y `available`. Efectos en una transacción: recurso → `in_service`, asignación con ETA, evento `resource_assigned`, y el incidente pasa a `resources_assigned` si estaba en `received` o `assessing`. Bloqueo `FOR UPDATE` en orden incidente → recurso.
- **«En el lugar»:** rellena `arrived_at` una sola vez y registra `resource_arrived`. **No cambia el estado del incidente.**
- **Retirar:** motivo obligatorio: `completed`, `not_needed`, `unavailable` (el usuario elige); `reassigned` e `incident_closed` (los pone el sistema). El recurso vuelve a `available`, o a `out_of_service` con `unavailable`. Si era el último activo y el incidente seguía en `resources_assigned`, este vuelve a `assessing`; en `in_progress` o `controlled` no cambia.
- **Reasignar:** explícita (`reassign: true`), confirmada en el frontend y atómica: retira en el incidente de origen (`reassigned`) y asigna en el de destino, con eventos y reglas aplicadas en ambos.
- **Cerrar o cancelar un incidente** retira automáticamente sus asignaciones activas (`incident_closed`); la confirmación de la interfaz enumera los recursos afectados.
- **Cambio manual de estado de un recurso asignado:** bloqueado (`resource_assigned`). Se retira desde el incidente.

**Estados del incidente**
- `resources_assigned` pasa a ser alcanzable, **solo automáticamente**: `received`/`assessing` → `resources_assigned` (primera asignación); `resources_assigned` → `assessing` (se retira la última). Manuales desde `resources_assigned`: `in_progress` y `cancelled` (con `incidents:close`). No aparece como acción manual en `allowed_transitions`.
- Los cambios automáticos se registran como `status_changed` con `cause: "assignment"`.

**Historial (`IncidentEvent`)**
- Nuevos: `resource_assigned` (`resource`, `resource_id`, `resource_type`, `eta`, `reassigned_from`), `resource_arrived` (`resource`, `resource_id`), `resource_released` (`resource`, `resource_id`, `reason`, `reassigned_to`). Siempre en la misma transacción que el cambio. Sin coordenadas de bases en el historial.

**API**
- `GET /incidents/{id}/assignments` (`incidents:read`): activas e historial, con la base de cada recurso.
- `GET /incidents/{id}/assignment-candidates` (`incidents:read` + `resources:read`): recursos activos con ETA, ordenados por ETA (sin base, al final), con los tipos sugeridos por el catálogo marcados; filtros `type`, `organization_id`, `include_assigned`. **Sin preselección.**
- `POST /incidents/{id}/assignments` (`assignments:manage`): `{resource_id, version, reassign?}`.
- `POST /assignments/{id}/arrival` (`assignments:update`) y `POST /assignments/{id}/release` (`assignments:manage`, `{reason, version}`), ambos con la `version` del incidente.
- Recursos: `base` (`LocationInput`/`LocationResponse`) sustituye a `municipality`; ficha y listado incluyen `current_assignment`. Incidente: `active_assignments_count`.
- Errores: 409 `resource_already_assigned`, `version_conflict`; 422 `resource_inactive`, `resource_not_available`, `incident_closed`, `assignment_already_released`, `assignment_already_arrived`, `resource_assigned`, `invalid_release_reason`; 404 `assignment_not_found`, `resource_not_found`. La base reutiliza `location_out_of_area` y `coordinates_incomplete`.

**Permisos**
- Nuevos: `assignments:manage` (asignar, retirar, reasignar) para admin y coordinator; `assignments:update` (marcar «en el lugar») para admin, coordinator y operator. El operador no asigna ni retira.

**Frontend**
- Ficha del incidente: panel «Recursos asignados» (código, tipo, organización, estado de la asignación, ETA estimada; acciones «En el lugar» y «Retirar» con motivo y confirmación) y diálogo «Asignar recurso» (candidatos por ETA, tipo sugerido marcado, filtros, opción de incluir asignados con aviso de reasignación; sin preselección).
- Panel lateral del centro de mando con los asignados y su ETA; indicador de recursos asignados en la lista de incidentes activos.
- Recursos: base (municipio y coordenadas, «Elegir en el mapa») en ficha y formulario, asignación actual con enlace al incidente, cambio de estado deshabilitado si está asignado.
- Confirmación de cierre/cancelación que enumera los recursos que se retirarán; textos del timeline para los eventos nuevos y la causa automática.
- `components/ops`: `EtaText` (siempre «estimado») y `ResourceMarker`, también en `/dev/design-system`.
- **Mapa:** solo las bases de los recursos asignados al incidente seleccionado (`ResourceMarker` distinto del de incidente, nombre accesible con código, tipo y ETA estimada). Sin líneas base → incidente (no hay rutas). Sin capa global de bases. «Ajustar a incidentes» incluye las bases visibles.

**Datos y Fase 5**
- Migraciones: bases de recursos (traslado del municipio), velocidad por tipo (valores en la migración), `resource_assignments` con su índice parcial, CHECK de `event_type` ampliado (el downgrade se niega si existen eventos nuevos).
- Seed: bases con coordenadas aproximadas dentro de Asturias, nunca sobre instalaciones reales; asignaciones simuladas coherentes con los estados. Requiere reiniciar la BD de desarrollo.
- Preparación para la Fase 5: todo cambio de asignación genera su `IncidentEvent` desde un servicio (el EventBus solo tendrá que publicarlos tras el commit); `origin` en la ETA y el diseño de `resource_positions`. Hueco conocido: los cambios manuales de estado de un recurso siguen sin evento.

### 2.9 Fuera de alcance en Fase 4 (no implementar)

Posiciones GPS o móviles de recursos (`resource_positions`), rutas por carretera, OSRM o cualquier API externa o de pago, WebSockets, polling, Redis o tiempo real, preselección o asignación automática, recomendaciones de IA/Ollama, hospitales, notificaciones, estadísticas, auditoría (`AuditLog`), simulador, historial completo de estados de recursos, capa global de bases en el mapa, tiempo de activación en la ETA, isócronas, zonas de cobertura, clustering y layout móvil.

Si una tarea de Fase 4 parece requerir algo de esta lista, **pregunta antes**.

### 2.10 Objetivos de diseño, acceso y distribución registrados

Registrados el 2026-10-09. El rediseño (§2.10.1) está **completado**. Los demás objetivos (§2.10.2 escritorio, §2.10.3 acceso remoto y §2.10.4 mapa operativo) **no autorizan implementar nada**: se abordarán cuando se autorice su etapa o fase y se apruebe su propuesta.

Idea general: **una sola aplicación web adaptable**, usada tanto en la sala de coordinación como en el portátil del coordinador, con el mapa como centro de la operación. No habrá dos aplicaciones distintas. El instalador de escritorio (§2.10.2) y el acceso remoto real (§2.10.3) son decisiones posteriores, y el rediseño no los espera.

#### 2.10.1 Etapa de rediseño del centro de mando (completada)

Etapa de diseño e implementación visual, posterior al cierre de la Fase 4. Implementada y aprobada el 2026-10-09. Solo frontend: sin cambios de backend, datos, reglas, permisos ni dependencias. No es una fase funcional y no amplía el alcance de §2. Por petición expresa, se implementó directamente y se aprobó tras revisarla en la aplicación, sin propuesta previa.

**Objetivo:** que el mapa sea el protagonista visual del centro de mando, en monitores grandes de sala y en portátiles. El layout móvil sigue fuera de alcance (§2.9).

**Distribución implementada:**

- **Barra superior compacta** (40 px): identidad de la aplicación, aviso de prototipo, estado de conexión y reloj.
- **Barra lateral plegable** a una columna de iconos. Los nombres siguen siendo accesibles y aparecen como tooltip. Empieza plegada por debajo de 1536 px de ancho.
- **Franja de indicadores** de una sola línea (`KpiTile` en variante `compact`) en lugar de tarjetas grandes.
- **Mapa en el centro, a sangre:**
  - Sin cabecera ni pie.
  - Recuento, «Datos simulados» y avisos (resultados truncados, incidentes sin coordenadas, seleccionado sin posición, error) superpuestos arriba a la izquierda.
  - Leyenda plegable abajo a la izquierda, plegada por defecto.
  - «Ajustar a incidentes» y «Centrar en Asturias» como botones de icono abajo a la derecha; el zoom de MapLibre, arriba a la derecha.
- **Dos columnas plegables a los lados del mapa** (`Dock`), no superpuestas: al plegarlas, el mapa recupera de verdad el espacio.
  - **Izquierda:** incidentes activos en filas compactas con prioridad, código, estado, título, municipio, recursos asignados y hora. Toda la fila selecciona, y la seleccionada se distingue con fondo y borde lateral.
  - **Derecha («Detalle y recursos»):** incidente seleccionado, con resumen y acciones de estado (cerrar y cancelar con su confirmación); recursos asignados, con asignar, reasignar, «en el lugar» y retirar; últimos eventos; y resumen de recursos por estado. Son los mismos componentes y permisos que la ficha completa.
  - Plegada, cada columna queda en un carril estrecho con su botón para mostrarla.
- **Selección:** seleccionar un incidente (en el mapa o en la lista) despliega el detalle si estaba plegado. Si al redimensionarse el mapa la selección queda fuera de la vista, el mapa la vuelve a centrar. Los recursos no se seleccionan en el mapa: los asignados se ven en el detalle, con enlace a su ficha.
- **Proporciones:**
  - Con las columnas plegadas, el mapa ocupa en torno al 90 % del ancho de trabajo.
  - Desplegadas, las columnas miden 288–384 px (izquierda) y 320–416 px (derecha), según el ancho de pantalla.
  - La página no se desplaza; cada columna tiene su propio scroll. Por debajo de 1024 px las columnas se apilan para no romperse, sin que eso sea un diseño móvil.
- **Estado de plegado:** preferencia local de cada navegador (`localStorage`, claves `ec.layout.*`, con try/catch). No va en la URL. La selección y los filtros siguen en la URL, compartidos por el mapa, la lista y el panel.
- **Se mantienen:**
  - el diseño oscuro y los tokens de §7;
  - la accesibilidad: teclado, foco, nombres accesibles y `aria-expanded` en los botones de plegado;
  - las transiciones de 150 ms, desactivadas con `prefers-reduced-motion`.

**Límites que siguen vigentes:** sin rutas, GPS, capas nuevas, tiempo real ni nada de §2.7 y §2.9. El rediseño no depende de Tauri, Electron ni del instalador (§2.10.2).

#### 2.10.2 Decisión futura de distribución: programa de escritorio

Objetivo: no cerrar la puerta a distribuir la aplicación como programa de escritorio para Windows (instalador).

- La aplicación **sigue siendo y funcionando como aplicación web**; el escritorio sería una forma adicional de distribuirla.
- El empaquetado reutilizaría el frontend React y el backend existentes.
- Cuando llegue el momento, se estudiará **Tauri como primera opción** y solo entonces se comparará con Electron.
- **Ahora no se hace nada para este objetivo:**
  - no se añaden dependencias;
  - no se integran Tauri ni Electron;
  - no se modifican la arquitectura del backend (§4) ni la base de datos.
- Lo único que pide hoy este objetivo es no introducir en el frontend nada que impida empaquetarlo más adelante. Si una decisión pudiera afectar a ese empaquetado, se señala y se pregunta.
- La elección de tecnología y la forma de empaquetar el backend y la base de datos son decisiones de §3 pendientes, que requerirán una propuesta escrita y una confirmación explícita.

#### 2.10.3 Objetivo futuro: acceso remoto seguro

Objetivo: que, si algún día se usa fuera de la red de la organización, solo puedan entrar las personas autorizadas. Poder acceder desde cualquier lugar no significa que cualquiera pueda entrar.

- **Salvedad de alcance:** hoy el proyecto es un **prototipo de demostración** que «no es un sistema real» (§1). Convertirlo en un sistema para coordinadores reales sería un cambio de naturaleza del proyecto, no solo de despliegue. Exigiría:
  1. revisar y reescribir el alcance de §1, con confirmación explícita;
  2. abordar las medidas de seguridad y despliegue pendientes.
- **Medidas pendientes** (no se implementan ahora):
  - límite de intentos de login (§2.5);
  - imágenes Docker de producción (§2.5);
  - despliegue seguro del backend;
  - comunicaciones protegidas con HTTPS, con la cookie de refresh `Secure` activada;
  - control de quién puede acceder, sobre la autenticación y el RBAC existentes.
- Hasta entonces, la aplicación sigue pensada para ejecutarse localmente con datos de demostración.

#### 2.10.4 Objetivo futuro: mapa operativo (dibujo y capas)

Registrado el 2026-10-09. **No autoriza implementar nada.** Requiere su propia fase o etapa, con propuesta técnica aprobada; el orden respecto a la Fase 5 está por decidir.

**Objetivo:** que el mapa ayude a coordinar y no solo muestre posiciones.

- **Dibujar y editar áreas:** perímetros de incendios y otras zonas afectadas.
- **Marcar elementos operativos:** cortes de carreteras, zonas de exclusión, zonas seguras y puntos de interés.
- **Asociar cada geometría a un incidente**, con tipo (de un catálogo, no libre), autor, fecha, estado y auditoría. Su evolución queda en el historial, sin sobrescribir sin rastro.
- **Mostrar y ocultar capas operativas** en el mapa.
- **Distinguir lo dibujado de lo oficial:** la información dibujada en el mapa no se confunde con datos oficiales o validados.

**Límites ya conocidos (a confirmar en la propuesta):**

- Hoy quedan fuera de alcance las capas nuevas y las geometrías que no sean puntos (§2.7 y §2.9); este objetivo los abriría de forma controlada.
- Una zona de exclusión sería **informativa**: sin alertas automáticas de entrada (eso exige posiciones reales, Fase 5) ni rutas que la eviten.
- Compartirlo en tiempo real llega con la Fase 5.
- Los permisos de dibujo deben encajar con la matriz y el ámbito de §2.11.
- Cualquier librería de dibujo para MapLibre (p. ej. Terra Draw) es una dependencia nueva que requiere aprobación.
- Las ayudas de cálculo (p. ej. la superficie de un perímetro con PostGIS) se etiquetan siempre como «estimado».

### 2.11 Etapa de roles, permisos y ámbito organizativo (completada)

Registrada y **aprobada el 2026-10-09**, con las decisiones D1–D11 de §2.11.5. Se implementa paso a paso (R.1–R.8): cada paso se verifica y se resume antes del siguiente. Objetivo: una central de coordinación única que trabaja con varias organizaciones (bomberos, sanitarios, policía…), separando **qué puede hacer** un usuario (rol → permisos) de **sobre qué organizaciones** puede hacerlo (ámbito). Todo se aplica en el backend; el frontend solo adapta la interfaz.

**Estado:** R.1–R.8 implementados y aprobados; D1–D11 aplicadas. Etapa **cerrada el 2026-10-09** (criterios en §11.5).

- **Escritura:** el ámbito se aplica al cambio de estado operativo de un recurso y a «en el lugar» (R.4), y a asignar, retirar y reasignar, con los candidatos filtrados (R.5).
- **Lectura (R.6):** el patrón (`require_read` → 404 y filtro en la consulta) está aplicado a la ficha y al listado de recursos. Con D4 no restringe a ningún rol.
- **Lecturas identificadas pero sin filtro**, porque con D4 no hace falta y su presentación con ámbitos limitados está por decidir: los recursos dentro de las asignaciones de un incidente, los recuentos del dashboard, las bases en el mapa y los códigos de recurso en el historial.

- **Interfaz (R.7):**
  - `/me` incluye `scope` (lectura y escritura: «todas» o una lista de organizaciones), calculado por el backend.
  - `canWriteOrganization` decide qué se muestra: botones de estado de un recurso, «En el lugar» y «Retirar» solo dentro del ámbito.
  - El alta del operador no tiene selector de incidente padre (D11).
  - `organization_out_of_scope` tiene su mensaje.
  - El backend falso de los tests aplica las mismas reglas.
  - Es solo ayuda visual: el backend sigue rechazando lo no autorizado.

- **Seed y cierre (R.8):** dos operadores de demo más (sanitario Gijón y sin organización); README con lo que puede hacer cada rol y el ámbito; verificación desde una copia limpia y contra la API en marcha.

Cierre confirmado el 2026-10-09.

#### 2.11.1 Situación actual (revisada en código)

**Permisos** (`app/core/permissions.py`, comprobados con `require_permission` en cada endpoint):

| Permiso | Operador | Coordinador | Admin | Endpoints |
|---|:-:|:-:|:-:|---|
| `incidents:read` | ✅ | ✅ | ✅ | listado, mapa, detalle, historial, asignaciones del incidente |
| `incidents:create` | ❌ | ✅ | ✅ | alta de incidente |
| `incidents:update` | ❌ | ✅ | ✅ | edición completa (`PATCH`), cambio de estado y **notas** |
| `incidents:close` | ❌ | ✅ | ✅ | cerrar o cancelar (comprobado en el servicio) |
| `resources:read` | ✅ | ✅ | ✅ | listado y ficha de recursos; candidatos y dashboard (junto con `incidents:read`) |
| `resources:update_status` | ✅ | ✅ | ✅ | cambio de estado operativo de un recurso |
| `resources:manage` | ❌ | ❌ | ✅ | alta, edición y desactivación de recursos |
| `organizations:read` | ❌ | ✅ | ✅ | listado de organizaciones |
| `assignments:manage` | ❌ | ✅ | ✅ | asignar, retirar, reasignar |
| `assignments:update` | ✅ | ✅ | ✅ | marcar «en el lugar» |

**Relaciones organizativas que existen:**

- `users.organization_id`: **una** organización por usuario, **nullable**.
- `resources.organization_id`: obligatoria; cada recurso pertenece a una organización.
- Asignaciones: sin columna propia; su organización es la del recurso.

**Lo que no existe:**

- **Ningún ámbito en la autorización.** Hoy cualquier operador cambia el estado de un recurso de cualquier organización, o marca su llegada, con solo conocer su identificador.
- **Ninguna relación incidente ↔ organización.** Los incidentes son de la central.
- **Ninguna forma de autorizar a un usuario sobre varias organizaciones.**
- **Ninguna gestión de usuarios ni de organizaciones** (ni API ni pantallas).

**Seed actual:**

- Admin y coordinador pertenecen al «Centro de Coordinación Demo»; el operador, a «Bomberos Demo Oviedo».
- Hay 18 recursos repartidos entre las 4 organizaciones.

**Diferencias con el objetivo:**

- El operador no puede crear incidentes ni añadir notas, porque las notas cuelgan de `incidents:update`.
- No existe la edición «solo de campos operativos».
- No hay ámbito organizativo.

#### 2.11.2 Matriz de permisos propuesta

Los permisos siguen en código (decisión de la Fase 1). Las novedades son `incidents:annotate`, `incidents:update_operational`, que se separa de la edición completa, y el **ámbito** de cada acción sobre recursos.

| Permiso | Operador | Coordinador | Admin | Ámbito |
|---|:-:|:-:|:-:|---|
| `incidents:read` | ✅ | ✅ | ✅ | Toda la central (ver D2) |
| `incidents:create` | ✅ **(nuevo para operador)** | ✅ | ✅ | — |
| `incidents:annotate` (notas, **nuevo**) | ✅ | ✅ | ✅ | — |
| `incidents:update_operational` (**nuevo**: solo campos operativos, ver D6) | ✅ | ✅ | ✅ | — |
| `incidents:update` (edición completa: prioridad, tipo, título, padre…) | ❌ | ✅ | ✅ | — |
| `incidents:change_status` (estados no finales; hoy dentro de `incidents:update`) | ❌ (ver D7) | ✅ | ✅ | — |
| `incidents:close` | ❌ | ✅ | ✅ | — |
| `resources:read` | ✅ | ✅ | ✅ | Ámbito de lectura (ver D4) |
| `resources:update_status` | ✅ | ✅ | ✅ | **Ámbito de escritura** |
| `resources:manage` | ❌ | ❌ | ✅ | Global (admin) |
| `assignments:manage` | ❌ | ✅ | ✅ | **Ámbito de escritura** sobre el recurso |
| `assignments:update` («en el lugar») | ✅ | ✅ | ✅ | **Ámbito de escritura** sobre el recurso (ver D9) |
| `organizations:read` | ❌ | ✅ | ✅ | — |
| Gestión de usuarios, roles y organizaciones | ❌ | ❌ | futuro | **Fuera de esta etapa** (etapa de seguridad, §2.10.3) |

#### 2.11.3 Solución técnica propuesta para el ámbito

- **`AccessScope` en el dominio** (`app/domain/access_scope.py`, puro y testeable):
  - Contiene `read_organizations` y `write_organizations`, cada uno como «todas» o como un conjunto de identificadores.
  - Lo calcula un único servicio a partir del usuario y lo inyecta una dependencia (`get_access_scope`). Ningún endpoint decide el ámbito por su cuenta.
- **Origen del ámbito en esta etapa** (sin tablas nuevas, ver D1):
  - Admin y coordinador: todas las organizaciones.
  - Operador: solo su `organization_id`.
  - Usuario sin organización: ámbito vacío, que deniega cualquier escritura sobre recursos.
  - Si más adelante hace falta autorizar a un coordinador sobre organizaciones concretas, solo cambia el origen de `AccessScope` (tabla de concesiones); los endpoints no se tocan.
- **Aplicación en los servicios, no en los routers:**
  - Cada escritura sobre un recurso comprueba la organización del recurso **después de cargarlo**, con el mismo bloqueo `FOR UPDATE` de la Fase 4. Si queda fuera del ámbito, lanza la excepción de dominio `OutOfScope` → 403 `organization_out_of_scope`. No se escribe nada ni se registra evento.
  - Lecturas fuera del ámbito de lectura: 404 `resource_not_found`, para no revelar que existe (ver D5).
- **Listados filtrados en el repositorio:** recursos, candidatos de asignación y resumen del dashboard se filtran con el ámbito de lectura, de modo que los recuentos no filtran datos ajenos.
- **Reasignación:** exige ámbito de escritura sobre el recurso; los incidentes de origen y de destino no tienen ámbito (D2).
- **`/auth/me`** devuelve el ámbito: lista de identificadores o «todas». El frontend lo usa para deshabilitar acciones; el backend lo vuelve a comprobar siempre.
- **Edición operativa:** el servicio compara los campos cambiados con los permitidos por `incidents:update_operational`. Si hay campos no permitidos, responde 403 `field_not_permitted` y no aplica ningún cambio parcial.
- **Sin cambios de esquema en la opción recomendada.** Solo cambian `permissions.py`, los servicios, los repositorios, los esquemas de `/me` y errores, el frontend y el seed (usuarios de demo adicionales).

#### 2.11.4 Pasos propuestos (cada uno se verifica, se resume y espera aprobación)

| Paso | Contenido | Criterios de aceptación y tests |
|---|---|---|
| R.1 Matriz en código | Permisos nuevos (`incidents:annotate`, `incidents:update_operational`, `incidents:change_status`) y matriz de §2.11.2; las notas pasan a `incidents:annotate` | Test de inventario: **cada ruta** de OpenAPI tiene declarados sus permisos y se llama con los 3 roles (sin el permiso → 403 `permission_denied`; con él → la autorización no la bloquea), y una ruta nueva sin declarar hace fallar el test. El operador crea incidentes y añade notas; recibe 403 en edición completa, cambio de estado, cierre y asignación |
| R.2 Edición operativa | Regla pura de campos permitidos por permiso; `PATCH` con comprobación por campo | Unit tests de la regla. El operador cambia campos operativos (200, `version` +1, evento) y recibe 403 `field_not_permitted` al enviar prioridad, título o padre (aunque sea el valor actual), **sin cambio parcial ni evento**; el tipo no lo cambia nadie (422) |
| R.3 `AccessScope` | Dominio puro, dependencia, cálculo por rol y organización | Unit tests: admin y coordinador → todas; operador → la suya; sin organización → vacío |
| R.4 Ámbito en escrituras del operador | Cambio de estado de recurso y «en el lugar» | Con el **identificador de un recurso ajeno**: 403 `organization_out_of_scope`, recurso, asignación e historial intactos. Con uno propio: 2xx. Prueba con dos operadores de organizaciones distintas |
| R.5 Ámbito en asignaciones | Asignar, retirar y reasignar con ámbito; candidatos filtrados | Coordinador con ámbito total asigna recursos de varias organizaciones al mismo incidente. Test con un ámbito restringido construido en el test (preparación para D1): 403 y sin efectos |
| R.6 Ámbito de lectura | Según D4: listado, ficha, candidatos, dashboard, bases en el mapa | Fuera del ámbito: 404 en la ficha, ausencia en listados y recuentos coherentes. Sin fugas en mensajes de error ni en logs |
| R.7 `/me` y frontend | Ámbito en `/me`; acciones deshabilitadas fuera del ámbito; alta y notas para el operador; formulario de edición operativa | `pnpm gen:api`; tests de frontend por rol y por organización. El backend falso imita las mismas reglas |
| R.8 Seed, documentación y cierre | Usuarios de demo adicionales (p. ej. un operador sanitario); README («qué puede hacer cada rol»), `docs/architecture.md`, clon limpio | Seed idempotente; criterios de esta tabla cumplidos; tests, `ruff`, `mypy`, `alembic check`, ESLint, tipos y build en verde |

#### 2.11.5 Decisiones (aprobadas el 2026-10-09 según las recomendaciones)

- **D1. Origen de la autorización multiorganización del coordinador.** No existe ninguna relación usuario ↔ varias organizaciones.
  - Recomendado: en esta etapa, el ámbito se deriva del rol (coordinador y admin = todas), detrás de `AccessScope`.
  - Alternativa: tabla de concesiones `user_organization_access`. Exige migración y, para gestionarla, la etapa de seguridad (no hay gestión de usuarios).
- **D2. Ámbito de los incidentes.** Los incidentes no tienen organización.
  - Recomendado: todos los usuarios de la central ven todos los incidentes.
  - Limitarlos exigiría una relación nueva (organizaciones participantes o jurisdicción) que hoy no existe y no se inventará sin aprobación.
- **D3. Usuarios sin organización** (`organization_id` es nullable). Recomendado: ámbito de escritura vacío para operadores; admin y coordinador no dependen de ella.
- **D4. Ámbito de lectura del operador.**
  - Recomendado: ve **todos** los recursos, porque la imagen operativa común lo necesita (mapa, asignados de otras organizaciones), y solo **modifica** los de su organización.
  - Alternativa: restringir también la lectura (paso R.6 completo).
- **D5. Respuesta fuera de ámbito.** Recomendado: 404 en lecturas (no revela existencia) y 403 `organization_out_of_scope` en escrituras sobre recursos visibles.
- **D6. Campos operativos del operador.** Propuesta: descripción, personas afectadas, ubicación (municipio, descripción y coordenadas) y `details`. Quedan fuera prioridad, tipo, título y padre. Requiere tu confirmación.
- **D7. ¿Puede el operador cambiar el estado** en pasos no finales (p. ej. `received` → `assessing`)? Recomendado: no, según el objetivo, que reserva prioridad y estado al coordinador.
  - **Precisión aprobada:** el operador **no** cambia el estado **del incidente**, pero **sí** actualiza el **estado operativo de los recursos de su organización** (`resources:update_status`, con ámbito de escritura). No se confunden los estados del incidente con los del recurso.
- **D8. Visibilidad de `/organizations` para el operador.** Recomendado: sigue en 403; su organización ya llega en `/me`.
- **D9. «En el lugar» de recursos ajenos.** Recomendado: el operador solo marca la llegada de recursos de su organización; el coordinador, de cualquiera.
- **D10. Prioridad inicial** (decidida al aprobar R.1). Quien no tiene `incidents:update` (el operador) crea los incidentes con la **prioridad por defecto del tipo** (`incident_types.default_priority`, obligatoria y única por tipo) y no puede elegirla: indicarla en el alta responde 403 `field_not_permitted`. Coordinador y admin pueden fijarla. Sin reglas de clasificación ni IA.
- **D11. Incidente padre en el alta (decidida: opción b).** Quien no tiene `incidents:update` (el operador) no puede indicar `parent_incident_id` al crear un incidente: un valor distinto de `null` responde 403 `field_not_permitted` y no se crea nada. Coordinador y admin sí pueden. Origen: la revisión final de R.2 detectó que el alta lo permitía.

**Fuera de esta etapa:** gestión de usuarios, roles y organizaciones; roles en base de datos o configurables; límite de intentos de login; auditoría (`AuditLog`); jurisdicción de incidentes; cualquier funcionalidad de §2.9.

---

## 3. Decisiones confirmadas

| Tema | Decisión |
|---|---|
| Región de la demo | Asturias (Oviedo, Gijón, Avilés como zonas principales) |
| Geodatos | PostgreSQL + PostGIS (activo a partir de Fase 3) |
| Mapas | MapLibre GL JS + OpenFreeMap. PMTiles local se evaluará más adelante para modo offline |
| Idioma | Solo español. Arquitectura preparada para i18n con react-i18next |
| IA | Proveedor basado en reglas, sin APIs de pago. Ollama local se evaluará como opcional en el futuro |
| Entidad central | `Incident` (en la interfaz se puede llamar "emergencia") |
| Núcleo de datos | `IncidentEvent` es la fuente de verdad del timeline, el tiempo real, las estadísticas y la auditoría |
| Tiempo real | Eventos emitidos por servicios → EventBus → WebSocket. Redis solo si hay varios workers |
| ETA | Distancia × factor de sinuosidad / velocidad media por tipo. Siempre etiquetada como "estimado" |
| Zona horaria | Almacenar en UTC (`timestamptz`). Mostrar en Europe/Madrid |

Estas decisiones no se cambian sin justificación escrita y confirmación explícita.

---

## 4. Arquitectura

```
Frontend (React SPA)
   │  REST (TanStack Query) + WebSocket (desde Fase 5)
   ▼
FastAPI
   api/v1/        → routers: validación, auth, permisos. SIN lógica de negocio
   services/      → lógica de negocio + emisión de eventos
   repositories/  → acceso a datos
   models/        → SQLAlchemy
   schemas/       → Pydantic (entrada/salida)
   ▼
PostgreSQL / PostGIS
```

### Estructura de carpetas

```
emergency-command/
├─ CLAUDE.md  README.md  docker-compose.yml  .env.example
├─ docs/
├─ backend/
│  ├─ pyproject.toml  alembic.ini  alembic/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/          config, security, permissions, logging
│  │  ├─ db/            session, base
│  │  ├─ models/        un fichero por entidad
│  │  ├─ schemas/
│  │  ├─ repositories/
│  │  ├─ services/
│  │  ├─ api/v1/        routers + deps.py
│  │  ├─ domain/        enums, reglas puras (sin I/O)
│  │  ├─ realtime/      (Fase 5)
│  │  ├─ simulation/    (Fase 7)
│  │  └─ ai/            (Fase 8)
│  ├─ seeds/            fixtures y seed.py (solo demo)
│  └─ tests/            unit/ integration/
└─ frontend/
   └─ src/
      ├─ app/           router, providers, layout
      ├─ components/ui/ shadcn (no modificar salvo necesidad justificada)
      ├─ components/ops/ componentes propios del sistema de diseño
      ├─ features/<módulo>/ api.ts, hooks.ts, components/, types.ts
      ├─ lib/           api-client, query-keys, format
      ├─ i18n/          config + locales/es.json
      ├─ types/api.ts   generado desde OpenAPI (openapi-typescript)
      └─ styles/        tokens.css
```

### Reglas de arquitectura

- Un router nunca accede directamente a la base de datos. Llama siempre a un servicio.
- Los servicios no conocen HTTP: nada de `Request`, `HTTPException` ni nada de FastAPI. Lanzan excepciones de dominio, y la capa API las traduce a respuestas HTTP.
- La API devuelve **códigos**, nunca textos traducidos (`"priority": "critical"`). El frontend traduce.
- Los tipos del frontend se generan desde el OpenAPI del backend. No dupliques tipos a mano.
- Las carpetas de fases futuras pueden existir vacías (con `__init__.py`), pero sin código.

---

## 5. Modelo de dominio (referencia para fases futuras)

En Fase 1 solo se implementan `roles`, `organizations` y `users`. El resto se documenta para que el diseño actual no lo impida.

### Incident: entidad central, no un framework genérico

- Los **tipos** son un catálogo en base de datos (`incident_types`), no un enum fijo. Cada fila guarda:
  - `code`, `category`, `icon` (nombre de Lucide);
  - `default_priority`, `suggested_resource_types`, `common_risks`;
  - `details_schema_key`, si el tipo tiene datos específicos.
- Los **estados** y las **prioridades** son enums fijos en código y comunes a todos los tipos, porque el flujo de trabajo debe ser uniforme.
  - Estados: `received`, `assessing`, `resources_assigned`, `in_progress`, `controlled`, `closed`, `cancelled`.
  - Prioridades: `critical`, `high`, `medium`, `low`.
- `parent_incident_id` (nullable) permite agrupar incidentes hijos bajo un incidente mayor.

### Reglas del campo `details` (JSONB)

- Solo contiene datos específicos de un tipo (p. ej. hectáreas afectadas, nivel de agua).
- Se valida con un esquema Pydantic registrado por tipo. Sin esquema, `details` debe ser `{}`.
- Nunca contiene datos que se filtren, ordenen o agreguen con frecuencia. Esos datos van en columnas propias (prioridad, estado, personas afectadas, ubicación…).
- Nunca contiene datos personales sensibles.

### Límites explícitos

- **No** modelar todavía grandes eventos planificados, evacuaciones ni catástrofes como flujos propios.
- **No** crear motores de workflow configurables, campos dinámicos en la interfaz ni constructores de formularios.
- Si una funcionalidad requiere más genericidad que lo descrito aquí, propónla y espera confirmación.

### Entidades previstas

`Role`, `Organization`, `User`, `Location`, `IncidentType`, `Incident`, `IncidentEvent` (solo inserción), `Resource` (base como `Location` 1:1 desde la Fase 4), `ResourceAssignment` (índice único parcial: una asignación activa por recurso), `Hospital`, `Notification` y `AuditLog`.

---

## 6. Seguridad

- Ningún secreto, contraseña ni token en el código ni en commits. Todo va en `.env`, documentado en `.env.example` con valores de ejemplo no válidos.
- Contraseñas siempre con Argon2. Nunca se registran ni se devuelven.
- No guardar tokens en `localStorage` ni en `sessionStorage`.
- Todos los endpoints protegidos por defecto. Los públicos (login, refresh, health) se declaran explícitamente.
- Autorización comprobada en backend. Ocultar elementos en el frontend es solo UX, no seguridad.
- Validación en ambos lados: Pydantic en backend, zod en formularios del frontend.
- CORS con orígenes explícitos desde `.env`. Nunca `*` junto con credenciales.
- Los logs no contienen contraseñas, tokens, cookies ni datos personales de afectados.
- Las acciones peligrosas o irreversibles requieren confirmación explícita en la interfaz.

---

## 7. Sistema de diseño

Interfaz oscura, densa y legible. Inspiración: centros de operaciones, software de dispatch, GIS y aviación.

### Tokens base (`tokens.css`, expuestos a Tailwind vía `@theme`)

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#0B0E13` | fondo de la aplicación |
| `--surface-1` | `#11151C` | paneles |
| `--surface-2` | `#171C25` | elementos elevados, hover |
| `--border` | `#232A36` | bordes |
| `--text` | `#E6EAF0` | texto principal |
| `--text-muted` | `#9AA4B2` | texto secundario |

### Colores de estado (solo para comunicar estado, nunca decorativos)

| Semántica | Color | Uso |
|---|---|---|
| critical | `#EF4444` | emergencia crítica |
| high | `#F97316` | prioridad alta |
| warning | `#EAB308` | advertencia |
| ok | `#22C55E` | disponible / normal |
| info | `#3B82F6` | información / en servicio |
| inactive | `#6B7280` | inactivo / desconectado |

Cada color tiene tres variantes: texto, fondo tenue y borde.

### Reglas visuales

- Tipografías:
  - Inter para la interfaz, con base de 13 px.
  - JetBrains Mono con cifras tabulares para códigos, horas y coordenadas.
- Medidas:
  - Rejilla de 4 px.
  - Filas de 32 px.
  - Radios de 4–6 px.
  - Bordes en lugar de sombras.
- El color nunca va solo. Siempre se acompaña de icono Lucide y texto (accesibilidad).
- La única animación permitida es el pulso de los elementos críticos, y respeta `prefers-reduced-motion`.
- Evitar:
  - gradientes y glassmorphism;
  - tarjetas gigantes;
  - estética SaaS genérica o de aplicación de chat;
  - colores arbitrarios.
- No esconder información crítica detrás de varios clics.
- Reutilizar `components/ops/` antes de crear componentes nuevos.

---

## 8. Datos de demostración y simulación

- Los datos de demo viven solo en `backend/seeds/` (y, más adelante, en `backend/app/simulation/`).
- Nunca hay datos falsos repartidos por componentes, servicios o routers.
- El seed es idempotente: se puede ejecutar varias veces sin duplicar datos.
- El simulador (Fase 7):
  - opera a través de los servicios, nunca escribiendo directamente en la base de datos;
  - se activa con `SIMULATION_ENABLED`;
  - marca sus eventos con `is_simulated = true`.
- Las credenciales de demo solo funcionan en entorno `development`, y se documentan en el README.
- Ningún teléfono, URL, endpoint ni nombre puede confundirse con un servicio real sin estar marcado como simulado.

---

## 9. IA (Fase 8, referencia)

- La IA **recomienda; nunca decide**. Sus resultados se etiquetan como "Recomendación".
- Ninguna asignación ni cambio de estado se aplica sin confirmación de un usuario humano.
- El operador siempre puede modificar o rechazar la recomendación.
- La IA va detrás de la interfaz `AIProvider`, con un proveedor basado en reglas por defecto.
- El sistema funciona completo sin IA.

---

## 10. Reglas operativas para Claude Code

### Antes de modificar código

1. Analiza la estructura actual del repositorio y las versiones instaladas.
2. Lee los ficheros que vas a tocar antes de editarlos.
3. Si la tarea implica una decisión arquitectónica no cubierta aquí, propónla y **espera confirmación**.

### Lo que puedes hacer sin preguntar

- Implementar lo que está dentro del alcance de la fase actual (§2).
- Crear ficheros y carpetas según la estructura de §4.
- Escribir y ejecutar tests, lint, type-check y build.
- Corregir errores que hayas introducido tú.

### Lo que requiere confirmación previa

- Instalar cualquier dependencia que no figure en este fichero, indicando por qué es necesaria y qué alternativas has descartado.
- Cambiar una tecnología, una versión mayor o una decisión de §3.
- Modificar el esquema de base de datos fuera de lo previsto en la fase.
- Borrar o reescribir ficheros existentes de forma sustancial.
- Tocar código no relacionado con la tarea.

### Lo que nunca debes hacer

- Hacer `git commit`, `git push` ni crear ramas o PRs, salvo que se te pida explícitamente.
- Conectar con servicios reales de emergencias o con APIs de pago.
- Introducir secretos, credenciales o tokens en el código.
- Implementar funcionalidades de fases futuras "porque era rápido".
- Desactivar tests, lint o comprobaciones de tipos para que algo pase.
- Usar `any` en TypeScript o `# type: ignore` sin un comentario que lo justifique.

### Documentación de librerías

- Antes de usar una librería nueva o una API que no hayas usado en este repo, consulta su documentación oficial actualizada mediante Context7 si está disponible.
- No asumas APIs de memoria. En particular, Tailwind v4, shadcn/ui, React Router, TanStack Query, SQLAlchemy 2 async y pydantic v2 han cambiado respecto a versiones anteriores.

### Calidad

- TypeScript en modo estricto y correctamente tipado.
- Backend tipado y verificado con `mypy`. Lint con `ruff`.
- Frontend con ESLint y Prettier.
- Después de cada cambio importante, ejecuta tests, lint, type-check y build.
- Si algo falla, corrígelo antes de continuar.
- No dupliques lógica. Reutiliza lo que ya existe.

---

## 11. Criterios de aceptación

### 11.1 Fase 1

La Fase 1 se considera terminada cuando (todos cumplidos y verificados al cierre, 2026-10-07):

- [x] `docker compose up` levanta `db`, `backend` y `frontend` sin errores desde un clon limpio, copiando `.env.example` a `.env`.
- [x] Las migraciones de Alembic se aplican desde cero y el seed crea los usuarios de demo.
- [x] Se puede iniciar sesión con cada uno de los tres roles.
- [x] El refresh automático funciona y el logout invalida la sesión.
- [x] Un usuario sin permiso recibe 403 en backend y no ve la opción en la navegación.
- [x] `/api/v1/health` responde, y la documentación OpenAPI está disponible en `/docs` en desarrollo.
- [x] El layout del centro de mando se renderiza con el sistema de diseño y estados vacíos, sin datos falsos.
- [x] `/dev/design-system` muestra los componentes base en todos sus estados, y no existe en el build de producción.
- [x] La extensión PostGIS está disponible, pero no hay ningún uso geográfico en código ni en migraciones de modelos.
- [x] Ningún texto visible está hardcodeado fuera de `es.json`.
- [x] Tests, lint, type-check y build pasan en backend y frontend.
- [x] El README permite a otra persona arrancar el proyecto sin ayuda.
- [x] No hay secretos en el repositorio.

### 11.2 Fase 2

La Fase 2 se considera terminada cuando (todos cumplidos y verificados al cierre, 2026-10-08):

- [x] `Incident`, `IncidentType` e `IncidentEvent` existen con migración; el historial es transaccional y de solo inserción.
- [x] Estados y prioridades son enums del backend expuestos por OpenAPI; las transiciones se validan en el servicio.
- [x] API de incidentes: alta, consulta, edición, cambios de estado y notas, con `details` validados por tipo, `parent_incident_id` e `is_simulated`.
- [x] Concurrencia optimista con `version`: una modificación con versión obsoleta recibe `409` y la interfaz lo gestiona.
- [x] `Resource` asociado a organizaciones, con tipos, estados y API de lista, detalle, alta, edición y cambio de estado.
- [x] RBAC aplicado en backend a incidentes, recursos y dashboard, y reflejado en la navegación y las acciones del frontend.
- [x] El centro de mando muestra KPIs, incidentes activos con filtros, panel lateral y resumen de recursos con datos reales de la API; el mapa sigue reservado.
- [x] Estados loading/empty/error en todas las pantallas; filtros y selección persistentes en la URL.
- [x] Seed idempotente de incidentes y recursos simulados de Asturias, todo marcado como simulado y sin datos que puedan confundirse con reales.
- [x] Tipos del frontend generados con `pnpm gen:api`; `PriorityCode` manual eliminado.
- [x] Ningún texto visible hardcodeado fuera de `es.json`; accesibilidad revisada.
- [x] Ningún elemento de §2.4 implementado (sin mapa, PostGIS espacial, asignaciones, ETA, tiempo real ni IA).
- [x] Tests (283 backend, 75 frontend), `ruff`, `mypy`, ESLint, type-check y build pasan; verificado desde un clon limpio.
- [x] README y `docs/architecture.md` actualizados, separando lo implementado de lo preparado.
- [x] Ninguna dependencia nueva durante la fase.

### 11.3 Fase 3

La Fase 3 se considera terminada cuando (todos cumplidos y verificados al cierre, 2026-10-08):

- [x] `Location` 1:1 con `Incident` (`location_id NOT NULL UNIQUE`), sin abstracciones para otras entidades.
- [x] `locations.geom` es `geometry(Point, 4326)` nullable con índice GiST, y es la única columna geográfica (test de metadatos).
- [x] La migración traslada la ubicación textual existente sin tocar `version`, `updated_at` ni el historial; el `downgrade` está probado con datos.
- [x] La API usa `location` anidada con coordenadas WGS84 validadas (rangos, ambas o ninguna, sin `NaN`, 6 decimales, área de Asturias) y códigos de error propios.
- [x] Cambiar la ubicación incrementa `version` una vez y registra `location_changed` con el antes y el después; una edición sin cambios no escribe nada.
- [x] `GET /incidents/map` devuelve GeoJSON con filtros, `bbox` sobre el índice GiST, `unlocated_total` y `truncated`, y no sustituye a `GET /incidents`.
- [x] Las coordenadas nunca aparecen en logs, excepciones ni respuestas de error de validación (tests).
- [x] Seed con coordenadas simuladas aproximadas, incidentes sin coordenadas a propósito, idempotente y validado con las reglas de la API.
- [x] Mapa funcional (MapLibre + OpenFreeMap `dark`) en el centro de mando, con carga diferida, atribución siempre visible y avisos si falla el mapa base o no hay WebGL2.
- [x] Marcadores compactos accesibles: color + icono de prioridad, borde de estado, código al seleccionar y en el tooltip, nombre accesible completo y simulado indicado.
- [x] Mapa ↔ lista ↔ panel por URL, filtros compartidos, centrado que respeta `prefers-reduced-motion` e incidentes sin coordenadas indicados y filtrables.
- [x] Coordenadas en el formulario con «Elegir en el mapa», minimapa en la ficha y `location_changed` en el historial.
- [x] Ningún elemento de §2.7 implementado.
- [x] Tests (352 backend, 95 frontend), `ruff`, `mypy`, `alembic check`, ESLint, type-check y build pasan; verificado desde un clon limpio.
- [x] README y `docs/architecture.md` actualizados.
- [x] Solo las dependencias aprobadas: `geoalchemy2` 0.20.0 y `maplibre-gl` 6.13.0.

### 11.4 Fase 4

La Fase 4 se considera terminada cuando (todos cumplidos y verificados al cierre, 2026-10-09):

- [x] Cada recurso tiene su base como `Location` 1:1 y el seed les da coordenadas válidas dentro de Asturias, sin instalaciones reales.
- [x] Cada tipo de recurso tiene velocidad media; la ETA es `ceil(haversine × 1.4 / velocidad × 60)`, con distancia de 1 decimal, `origin: "base"`, calculada localmente y sin tiempo de activación.
- [x] La ETA se guarda al asignar y no cambia retroactivamente; siempre se presenta como «estimado».
- [x] Un recurso nunca tiene dos asignaciones activas: lo garantiza el índice único parcial y se prueba con concurrencia; un incidente admite varios recursos.
- [x] Asignar, marcar «en el lugar», retirar (con motivo obligatorio) y reasignar (explícita y atómica) actualizan de forma coherente recurso, incidente, `version` e historial en una sola transacción.
- [x] `resources_assigned` solo se alcanza y se abandona automáticamente según §2.8; `arrived_at` no cambia el estado del incidente.
- [x] Cerrar o cancelar un incidente retira automáticamente sus asignaciones activas, con confirmación previa que enumera los recursos.
- [x] Ningún cambio manual de estado deja un recurso en contradicción con sus asignaciones.
- [x] Permisos de §2.8 aplicados en el backend y reflejados en la interfaz (el operador marca la llegada, pero no asigna ni retira).
- [x] Candidatos ordenados por ETA con tipos sugeridos marcados, sin preselección ni asignación automática.
- [x] Ficha del incidente, panel lateral, ficha de recurso y mapa (solo bases de los asignados al incidente seleccionado) muestran asignaciones y ETA con datos reales.
- [x] Ningún elemento de §2.9 implementado.
- [x] Tests (425 backend, 105 frontend), `ruff`, `mypy`, `alembic check`, ESLint, type-check y build pasan; verificado desde un clon limpio.
- [x] README y `docs/architecture.md` actualizados.

### 11.5 Etapa de roles, permisos y ámbito organizativo

La etapa se considera terminada cuando (todos cumplidos y verificados al cierre, 2026-10-09):

- [x] Matriz de permisos de §2.11.2 en código; cada ruta de la API declara sus permisos en un test de inventario que falla ante una ruta nueva sin declarar.
- [x] El operador registra incidentes y añade notas; no cambia el estado del incidente, no lo cierra ni asigna, retira o reasigna recursos.
- [x] Edición operativa: el operador solo modifica descripción, personas afectadas, ubicación y `details`; cualquier otro campo enviado responde 403 `field_not_permitted` sin cambios parciales ni eventos (D6).
- [x] En el alta, el operador recibe la prioridad por defecto del tipo y no indica prioridad ni incidente padre (D10, D11).
- [x] `AccessScope` con una regla explícita por rol, que falla de forma cerrada ante un rol desconocido; lo calcula el backend y `/me` lo expone.
- [x] Ámbito de escritura aplicado en los servicios (estado operativo de recursos, «en el lugar», asignar, retirar, reasignar y candidatos), antes de modificar nada; fuera de ámbito, 403 `organization_out_of_scope`. Probado con el identificador de un recurso de otra organización y con un operador sin organización.
- [x] D4 se mantiene: todos leen todas las organizaciones; el patrón de lectura (`require_read` → 404 y filtro en la consulta) está aplicado a la ficha y al listado de recursos.
- [x] La interfaz refleja permisos y ámbito (acciones ocultas, motivo visible, mensajes de error) y el backend falso aplica las mismas reglas.
- [x] Seed con operadores de dos organizaciones y uno sin organización, idempotente.
- [x] Tests (510 backend, 122 frontend), `ruff`, `mypy`, `alembic check`, ESLint, type-check, Prettier y build pasan; verificado desde una copia limpia (325 ficheros versionables, dependencias instaladas desde cero e imágenes Docker construidas) y contra la API en marcha con los usuarios del seed (403 `organization_out_of_scope` y `field_not_permitted` donde corresponde, sin cambios en los datos).
- [x] Sin cambios de esquema ni migraciones; sin gestión de usuarios u organizaciones, roles configurables, auditoría ni jurisdicción de incidentes.
- [x] README, `docs/architecture.md` y esta sección actualizados.

---

## 12. Formato obligatorio del resumen al terminar cada fase

Al terminar una fase (o cuando se te pida un resumen), responde con esta estructura y detente hasta recibir confirmación:

```
## Resumen de Fase N

### Hecho
- Qué se ha implementado, agrupado por backend / frontend / infraestructura / docs.

### Ficheros principales
- Ficheros creados o modificados de forma relevante (no listar todos).

### Dependencias añadidas
- Nombre, versión y motivo. "Ninguna" si no hay.

### Verificación
- Comandos ejecutados (tests, lint, type-check, build) y su resultado.
- Criterios de aceptación: cumplidos / no cumplidos.

### Decisiones tomadas
- Decisiones técnicas menores tomadas durante la fase y su motivo.

### Pendiente o conocido
- Limitaciones, deuda técnica o problemas detectados.

### Decisiones que necesito de ti
- Preguntas concretas antes de pasar a la siguiente fase.
```

No empieces la siguiente fase sin confirmación explícita. Cuando se confirme, se actualizará §2 de este fichero con el nuevo alcance.
