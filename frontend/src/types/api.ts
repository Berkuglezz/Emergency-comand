/**
 * Tipos de la API de Emergency Command.
 * Generado por `pnpm gen:api` desde el OpenAPI 3.1.0 de "Emergency Command API" v0.1.0.
 * NO EDITAR A MANO: regenerar tras cambiar el backend.
 */

export interface paths {
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Health
         * @description Estado del backend y de sus dependencias. Público.
         */
        get: operations["get_health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Login */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh */
        post: operations["refresh_api_v1_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Me
         * @description Perfil, permisos y ámbito organizativo efectivos del usuario autenticado.
         */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/organizations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Organizations */
        get: operations["list_organizations_api_v1_organizations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incident-types": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Incident Types */
        get: operations["list_incident_types_api_v1_incident_types_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Incidents
         * @description Incidentes. Por defecto solo los activos (`active=false` incluye cerrados y cancelados).
         */
        get: operations["list_incidents_api_v1_incidents_get"];
        put?: never;
        /** Create Incident */
        post: operations["create_incident_api_v1_incidents_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/map": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Map Incidents
         * @description Incidentes con coordenadas como `FeatureCollection` GeoJSON, con los mismos
         *     filtros de estado y prioridad que el listado (por defecto, solo activos).
         *
         *     Datos mínimos para dibujar; el listado sigue siendo `GET /incidents`. Tope
         *     de 1.000 elementos (`truncated`); `unlocated_total` cuenta los que cumplen
         *     los filtros sin coordenadas.
         */
        get: operations["map_incidents_api_v1_incidents_map_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Incident */
        get: operations["get_incident_api_v1_incidents__incident_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Incident */
        patch: operations["update_incident_api_v1_incidents__incident_id__patch"];
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Change Incident Status
         * @description Cambia el estado. Cerrar o cancelar exige además `incidents:close`.
         */
        post: operations["change_incident_status_api_v1_incidents__incident_id__status_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Incident Events
         * @description Historial funcional del incidente (timeline), en orden cronológico.
         */
        get: operations["list_incident_events_api_v1_incidents__incident_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Add Incident Note */
        post: operations["add_incident_note_api_v1_incidents__incident_id__notes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/assignments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Incident Assignments
         * @description Asignaciones del incidente: activas primero y después el historial.
         */
        get: operations["list_incident_assignments_api_v1_incidents__incident_id__assignments_get"];
        put?: never;
        /**
         * Assign Resource
         * @description Asigna un recurso disponible. Con `reassign: true`, si está asignado a otro
         *     incidente, se retira de él y se asigna a este en la misma transacción.
         *     Recurso fuera del ámbito de escritura del usuario: 403 `organization_out_of_scope`.
         */
        post: operations["assign_resource_api_v1_incidents__incident_id__assignments_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/incidents/{incident_id}/assignment-candidates": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Assignment Candidates
         * @description Recursos asignables ordenados por ETA **estimada** (sin estimación, al final),
         *     con los tipos sugeridos marcados. Ayuda a la decisión: no se preselecciona ninguno.
         *     `include_assigned=true` añade los asignados a otros incidentes (exigen reasignar).
         *     Solo recursos del ámbito de escritura del usuario.
         */
        get: operations["list_assignment_candidates_api_v1_incidents__incident_id__assignment_candidates_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/assignments/{assignment_id}/arrival": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark Arrival
         * @description Marca que el recurso ha llegado al lugar. No cambia el estado del incidente.
         *     Recurso fuera del ámbito de escritura del usuario: 403 `organization_out_of_scope`.
         */
        post: operations["mark_arrival_api_v1_assignments__assignment_id__arrival_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/assignments/{assignment_id}/release": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Release Resource
         * @description Retira el recurso con un motivo (`completed`, `not_needed` o `unavailable`).
         *     Recurso fuera del ámbito de escritura del usuario: 403 `organization_out_of_scope`.
         */
        post: operations["release_resource_api_v1_assignments__assignment_id__release_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resource-types": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Resource Types */
        get: operations["list_resource_types_api_v1_resource_types_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Resources
         * @description Recursos del ámbito de lectura del usuario (con D4, todas las organizaciones).
         *     Por defecto solo los activos (`active=false` incluye los desactivados).
         */
        get: operations["list_resources_api_v1_resources_get"];
        put?: never;
        /** Create Resource */
        post: operations["create_resource_api_v1_resources_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/resources/{resource_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Resource
         * @description Ficha del recurso. Fuera del ámbito de lectura: 404, como si no existiera.
         */
        get: operations["get_resource_api_v1_resources__resource_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Resource
         * @description Edita la ficha (incluida la desactivación con `is_active`). No cambia el estado.
         */
        patch: operations["update_resource_api_v1_resources__resource_id__patch"];
        trace?: never;
    };
    "/api/v1/resources/{resource_id}/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Change Resource Status
         * @description Estado operativo del recurso. Fuera del ámbito de escritura del usuario:
         *     403 `organization_out_of_scope`.
         */
        post: operations["change_resource_status_api_v1_resources__resource_id__status_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Dashboard Summary
         * @description KPIs del centro de mando calculados con los datos actuales.
         */
        get: operations["get_dashboard_summary_api_v1_dashboard_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AccessScopeResponse
         * @description Ámbito organizativo efectivo (CLAUDE.md §2.11). Lo calcula el backend; el
         *     cliente solo lo usa para adaptar la interfaz y el backend lo vuelve a
         *     comprobar en cada petición.
         */
        AccessScopeResponse: {
            read: components["schemas"]["OrganizationAccessResponse"];
            write: components["schemas"]["OrganizationAccessResponse"];
        };
        /** AssignedResource */
        AssignedResource: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Name */
            name: string;
            status: components["schemas"]["ResourceStatus"];
            type: components["schemas"]["ResourceTypeResponse"];
            organization: components["schemas"]["OrganizationSummary"];
            base: components["schemas"]["LocationResponse"];
            /** Is Simulated */
            is_simulated: boolean;
        };
        /** AssignmentArrival */
        AssignmentArrival: {
            /** Version */
            version: number;
        };
        /**
         * AssignmentCandidate
         * @description Recurso que se puede asignar, con su ETA estimada desde la base. Es
         *     ayuda a la decisión: la lista se ordena por ETA, pero nunca se preselecciona
         *     ni se asigna nada automáticamente.
         */
        AssignmentCandidate: {
            resource: components["schemas"]["AssignedResource"];
            eta: components["schemas"]["EtaResponse"] | null;
            eta_unavailable: components["schemas"]["EtaUnavailable"] | null;
            /** Suggested */
            suggested: boolean;
            current_incident: components["schemas"]["IncidentCodeRef"] | null;
        };
        /** AssignmentCreate */
        AssignmentCreate: {
            /**
             * Resource Id
             * Format: uuid
             */
            resource_id: string;
            /** Version */
            version: number;
            /**
             * Reassign
             * @default false
             */
            reassign: boolean;
        };
        /** AssignmentRelease */
        AssignmentRelease: {
            /** Version */
            version: number;
            reason: components["schemas"]["ReleaseReason"];
        };
        /** AssignmentResponse */
        AssignmentResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            resource: components["schemas"]["AssignedResource"];
            /**
             * Assigned At
             * Format: date-time
             */
            assigned_at: string;
            /** Arrived At */
            arrived_at: string | null;
            /** Released At */
            released_at: string | null;
            release_reason: components["schemas"]["ReleaseReason"] | null;
            eta: components["schemas"]["EtaResponse"] | null;
            /** Is Simulated */
            is_simulated: boolean;
        };
        /**
         * ComponentStatus
         * @enum {string}
         */
        ComponentStatus: "ok" | "unavailable";
        /**
         * CurrentAssignment
         * @description Asignación activa de un recurso.
         */
        CurrentAssignment: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Incident Id
             * Format: uuid
             */
            incident_id: string;
            /** Incident Code */
            incident_code: string;
            /**
             * Assigned At
             * Format: date-time
             */
            assigned_at: string;
            /** Arrived At */
            arrived_at: string | null;
            eta: components["schemas"]["EtaResponse"] | null;
        };
        /** DashboardSummary */
        DashboardSummary: {
            /**
             * Generated At
             * Format: date-time
             */
            generated_at: string;
            incidents: components["schemas"]["IncidentKpis"];
            resources: components["schemas"]["ResourceKpis"];
        };
        /**
         * ErrorResponse
         * @description Cuerpo de los errores de la API. `detail` es un código, no un texto.
         */
        ErrorResponse: {
            /** Detail */
            detail: string;
        };
        /**
         * EtaOrigin
         * @enum {string}
         */
        EtaOrigin: "base" | "last_position";
        /**
         * EtaResponse
         * @description ETA **estimada** (distancia * sinuosidad / velocidad media del tipo).
         *     `distance_km` es la distancia estimada por carretera.
         */
        EtaResponse: {
            /** Minutes */
            minutes: number;
            /** Distance Km */
            distance_km: number;
            origin: components["schemas"]["EtaOrigin"];
        };
        /**
         * EtaUnavailable
         * @description Motivo por el que no se puede estimar.
         * @enum {string}
         */
        EtaUnavailable: "incident_without_coordinates" | "resource_without_position";
        /** EventActor */
        EventActor: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Full Name */
            full_name: string;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthResponse */
        HealthResponse: {
            status: components["schemas"]["HealthStatus"];
            database: components["schemas"]["ComponentStatus"];
        };
        /**
         * HealthStatus
         * @enum {string}
         */
        HealthStatus: "ok" | "degraded";
        /**
         * IncidentCategory
         * @enum {string}
         */
        IncidentCategory: "fire" | "traffic" | "medical" | "rescue" | "weather" | "hazmat" | "geological";
        /** IncidentCodeRef */
        IncidentCodeRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
        };
        /** IncidentCreate */
        IncidentCreate: {
            /**
             * Type Id
             * Format: uuid
             */
            type_id: string;
            /** Title */
            title: string;
            /** Description */
            description?: string | null;
            priority?: components["schemas"]["IncidentPriority"] | null;
            location: components["schemas"]["LocationInput"];
            /** Affected People */
            affected_people?: number | null;
            /** Details */
            details?: {
                [key: string]: unknown;
            };
            /** Parent Incident Id */
            parent_incident_id?: string | null;
        };
        /** IncidentDetail */
        IncidentDetail: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Title */
            title: string;
            status: components["schemas"]["IncidentStatus"];
            priority: components["schemas"]["IncidentPriority"];
            type: components["schemas"]["IncidentTypeSummary"];
            location: components["schemas"]["LocationResponse"];
            /** Affected People */
            affected_people: number | null;
            /** Parent Incident Id */
            parent_incident_id: string | null;
            /** Is Simulated */
            is_simulated: boolean;
            /** Version */
            version: number;
            /**
             * Reported At
             * Format: date-time
             */
            reported_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * Active Assignments
             * @default 0
             */
            active_assignments: number;
            /** Description */
            description: string | null;
            /** Details */
            details: {
                [key: string]: unknown;
            };
            parent: components["schemas"]["IncidentRef"] | null;
            /** Children */
            children: components["schemas"]["IncidentRef"][];
            /** Closed At */
            closed_at: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Allowed Transitions */
            allowed_transitions: components["schemas"]["IncidentStatus"][];
        };
        /** IncidentEventResponse */
        IncidentEventResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            event_type: components["schemas"]["IncidentEventType"];
            /**
             * Occurred At
             * Format: date-time
             */
            occurred_at: string;
            actor: components["schemas"]["EventActor"] | null;
            /** Payload */
            payload: {
                [key: string]: unknown;
            };
            /** Is Simulated */
            is_simulated: boolean;
        };
        /**
         * IncidentEventType
         * @description Tipos de entrada del historial funcional del incidente (timeline).
         * @enum {string}
         */
        IncidentEventType: "incident_created" | "status_changed" | "priority_changed" | "incident_updated" | "note_added" | "parent_changed" | "location_changed" | "resource_assigned" | "resource_arrived" | "resource_released";
        /** IncidentKpis */
        IncidentKpis: {
            /** Active Total */
            active_total: number;
            /** By Priority */
            by_priority: {
                [key: string]: number;
            };
            /** By Status */
            by_status: {
                [key: string]: number;
            };
            /** Affected People */
            affected_people: number;
            /** Reported Last 24H */
            reported_last_24h: number;
        };
        /**
         * IncidentMapCollection
         * @description `FeatureCollection` GeoJSON con dos miembros propios: incidentes que
         *     cumplen los filtros pero no tienen coordenadas, y si se alcanzó el tope.
         */
        IncidentMapCollection: {
            /**
             * Type
             * @default FeatureCollection
             * @constant
             */
            type: "FeatureCollection";
            /** Features */
            features: components["schemas"]["IncidentMapFeature"][];
            /** Unlocated Total */
            unlocated_total: number;
            /** Truncated */
            truncated: boolean;
        };
        /** IncidentMapFeature */
        IncidentMapFeature: {
            /**
             * Type
             * @default Feature
             * @constant
             */
            type: "Feature";
            geometry: components["schemas"]["PointGeometry"];
            properties: components["schemas"]["IncidentMapProperties"];
        };
        /**
         * IncidentMapProperties
         * @description Lo mínimo para dibujar y seleccionar; el detalle sale de `GET /incidents/{id}`.
         */
        IncidentMapProperties: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Title */
            title: string;
            status: components["schemas"]["IncidentStatus"];
            priority: components["schemas"]["IncidentPriority"];
            /** Type Code */
            type_code: string;
            /** Type Icon */
            type_icon: string;
            /** Is Simulated */
            is_simulated: boolean;
        };
        /** IncidentNoteCreate */
        IncidentNoteCreate: {
            /** Text */
            text: string;
        };
        /** IncidentPage */
        IncidentPage: {
            /** Items */
            items: components["schemas"]["IncidentSummary"][];
            /** Total */
            total: number;
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
        };
        /**
         * IncidentPriority
         * @enum {string}
         */
        IncidentPriority: "critical" | "high" | "medium" | "low";
        /**
         * IncidentRef
         * @description Referencia breve a otro incidente (padre o hijos).
         */
        IncidentRef: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Title */
            title: string;
            status: components["schemas"]["IncidentStatus"];
            priority: components["schemas"]["IncidentPriority"];
        };
        /**
         * IncidentStatus
         * @enum {string}
         */
        IncidentStatus: "received" | "assessing" | "resources_assigned" | "in_progress" | "controlled" | "closed" | "cancelled";
        /** IncidentStatusChange */
        IncidentStatusChange: {
            status: components["schemas"]["IncidentStatus"];
            /** Version */
            version: number;
            /** Reason */
            reason?: string | null;
        };
        /** IncidentSummary */
        IncidentSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Title */
            title: string;
            status: components["schemas"]["IncidentStatus"];
            priority: components["schemas"]["IncidentPriority"];
            type: components["schemas"]["IncidentTypeSummary"];
            location: components["schemas"]["LocationResponse"];
            /** Affected People */
            affected_people: number | null;
            /** Parent Incident Id */
            parent_incident_id: string | null;
            /** Is Simulated */
            is_simulated: boolean;
            /** Version */
            version: number;
            /**
             * Reported At
             * Format: date-time
             */
            reported_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * Active Assignments
             * @default 0
             */
            active_assignments: number;
        };
        /** IncidentTypeResponse */
        IncidentTypeResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            category: components["schemas"]["IncidentCategory"];
            /** Icon */
            icon: string;
            default_priority: components["schemas"]["IncidentPriority"];
            /** Suggested Resource Types */
            suggested_resource_types: string[];
            /** Common Risks */
            common_risks: string[];
            /** Details Schema Key */
            details_schema_key: string | null;
            /** Is Active */
            is_active: boolean;
        };
        /** IncidentTypeSummary */
        IncidentTypeSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            category: components["schemas"]["IncidentCategory"];
            /** Icon */
            icon: string;
        };
        /**
         * IncidentUpdate
         * @description Edición parcial: solo se modifican los campos enviados. `version` es
         *     obligatoria (bloqueo optimista). El tipo no se puede cambiar.
         */
        IncidentUpdate: {
            /** Version */
            version: number;
            /** Title */
            title?: string | null;
            /** Description */
            description?: string | null;
            priority?: components["schemas"]["IncidentPriority"] | null;
            location?: components["schemas"]["LocationInput"] | null;
            /** Affected People */
            affected_people?: number | null;
            /** Details */
            details?: {
                [key: string]: unknown;
            } | null;
            /** Parent Incident Id */
            parent_incident_id?: string | null;
        };
        /**
         * LocationInput
         * @description Ubicación completa: en una edición sustituye a la anterior (omitir las
         *     coordenadas las borra). Coordenadas: ambas o ninguna, y dentro del área de
         *     la demo (lo comprueba el servicio: `coordinates_incomplete`,
         *     `location_out_of_area`).
         */
        LocationInput: {
            /** Municipality */
            municipality: string;
            /** Description */
            description?: string | null;
            /** Latitude */
            latitude?: number | null;
            /** Longitude */
            longitude?: number | null;
        };
        /** LocationResponse */
        LocationResponse: {
            /** Municipality */
            municipality: string;
            /** Description */
            description: string | null;
            /** Latitude */
            latitude: number | null;
            /** Longitude */
            longitude: number | null;
        };
        /** LoginRequest */
        LoginRequest: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** MeResponse */
        MeResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Email */
            email: string;
            /** Full Name */
            full_name: string;
            role: components["schemas"]["RoleCode"];
            /** Permissions */
            permissions: components["schemas"]["Permission"][];
            organization: components["schemas"]["OrganizationSummary"] | null;
            scope: components["schemas"]["AccessScopeResponse"];
        };
        /**
         * OrganizationAccessResponse
         * @description Organizaciones alcanzables: todas, o la lista indicada (quizá vacía).
         */
        OrganizationAccessResponse: {
            /** All Organizations */
            all_organizations: boolean;
            /** Organization Ids */
            organization_ids: string[];
        };
        /** OrganizationResponse */
        OrganizationResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Name */
            name: string;
            /** Is Simulated */
            is_simulated: boolean;
            /** Is Active */
            is_active: boolean;
        };
        /** OrganizationSummary */
        OrganizationSummary: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Name */
            name: string;
            /** Is Simulated */
            is_simulated: boolean;
        };
        /**
         * Permission
         * @enum {string}
         */
        Permission: "incidents:read" | "incidents:create" | "incidents:update" | "incidents:update_operational" | "incidents:annotate" | "incidents:change_status" | "incidents:close" | "resources:read" | "resources:update_status" | "resources:manage" | "organizations:read" | "assignments:manage" | "assignments:update";
        /** PointGeometry */
        PointGeometry: {
            /**
             * Type
             * @default Point
             * @constant
             */
            type: "Point";
            /** Coordinates */
            coordinates: [
                number,
                number
            ];
        };
        /**
         * ReleaseReason
         * @description Motivo de la retirada de un recurso de un incidente.
         * @enum {string}
         */
        ReleaseReason: "completed" | "not_needed" | "unavailable" | "reassigned" | "incident_closed";
        /**
         * ResourceCategory
         * @enum {string}
         */
        ResourceCategory: "fire" | "rescue" | "medical" | "command" | "civil_protection" | "logistics";
        /** ResourceCreate */
        ResourceCreate: {
            /** Code */
            code: string;
            /** Name */
            name: string;
            /**
             * Type Id
             * Format: uuid
             */
            type_id: string;
            /**
             * Organization Id
             * Format: uuid
             */
            organization_id: string;
            base: components["schemas"]["LocationInput"];
            status?: components["schemas"]["ResourceStatus"] | null;
        };
        /** ResourceKpis */
        ResourceKpis: {
            /** Active Total */
            active_total: number;
            /** By Status */
            by_status: {
                [key: string]: number;
            };
            /** Inactive Total */
            inactive_total: number;
        };
        /** ResourcePage */
        ResourcePage: {
            /** Items */
            items: components["schemas"]["ResourceResponse"][];
            /** Total */
            total: number;
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
        };
        /** ResourceResponse */
        ResourceResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            /** Name */
            name: string;
            type: components["schemas"]["ResourceTypeResponse"];
            organization: components["schemas"]["OrganizationSummary"];
            status: components["schemas"]["ResourceStatus"];
            /**
             * Status Changed At
             * Format: date-time
             */
            status_changed_at: string;
            base: components["schemas"]["LocationResponse"];
            current_assignment?: components["schemas"]["CurrentAssignment"] | null;
            /** Is Active */
            is_active: boolean;
            /** Is Simulated */
            is_simulated: boolean;
            /** Version */
            version: number;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * ResourceStatus
         * @enum {string}
         */
        ResourceStatus: "available" | "in_service" | "out_of_service";
        /** ResourceStatusChange */
        ResourceStatusChange: {
            status: components["schemas"]["ResourceStatus"];
            /** Version */
            version: number;
        };
        /** ResourceTypeResponse */
        ResourceTypeResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Code */
            code: string;
            category: components["schemas"]["ResourceCategory"];
            /** Icon */
            icon: string;
            /** Average Speed Kmh */
            average_speed_kmh: number;
            /** Is Active */
            is_active: boolean;
        };
        /**
         * ResourceUpdate
         * @description Edición parcial de la ficha. `version` es obligatoria (bloqueo
         *     optimista). El código no se puede cambiar; el estado tiene su propio
         *     endpoint y permiso.
         */
        ResourceUpdate: {
            /** Version */
            version: number;
            /** Name */
            name?: string | null;
            /** Type Id */
            type_id?: string | null;
            /** Organization Id */
            organization_id?: string | null;
            base?: components["schemas"]["LocationInput"] | null;
            /** Is Active */
            is_active?: boolean | null;
        };
        /**
         * RoleCode
         * @enum {string}
         */
        RoleCode: "admin" | "coordinator" | "operator";
        /**
         * TokenResponse
         * @description El refresh token no aparece aquí: viaja solo en una cookie httpOnly.
         */
        TokenResponse: {
            /** Access Token */
            access_token: string;
            /**
             * Token Type
             * @default bearer
             * @constant
             */
            token_type: "bearer";
            /** Expires In */
            expires_in: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    get_health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_api_v1_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                ec_refresh_token?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: {
                ec_refresh_token?: string | null;
            };
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_organizations_api_v1_organizations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrganizationResponse"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_incident_types_api_v1_incident_types_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentTypeResponse"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_incidents_api_v1_incidents_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["IncidentStatus"][] | null;
                priority?: components["schemas"]["IncidentPriority"][] | null;
                type?: string | null;
                active?: boolean;
                q?: string | null;
                parent_id?: string | null;
                has_coordinates?: boolean | null;
                sort?: "priority" | "-reported_at" | "reported_at" | "-updated_at";
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentPage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_incident_api_v1_incidents_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    map_incidents_api_v1_incidents_map_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["IncidentStatus"][] | null;
                priority?: components["schemas"]["IncidentPriority"][] | null;
                active?: boolean;
                /** @description Rectángulo `minLon,minLat,maxLon,maxLat` (WGS84, orden GeoJSON). */
                bbox?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentMapCollection"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_incident_api_v1_incidents__incident_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    update_incident_api_v1_incidents__incident_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    change_incident_status_api_v1_incidents__incident_id__status_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentStatusChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_incident_events_api_v1_incidents__incident_id__events_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentEventResponse"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    add_incident_note_api_v1_incidents__incident_id__notes_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IncidentNoteCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentEventResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_incident_assignments_api_v1_incidents__incident_id__assignments_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentResponse"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    assign_resource_api_v1_incidents__incident_id__assignments_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignmentCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_assignment_candidates_api_v1_incidents__incident_id__assignment_candidates_get: {
        parameters: {
            query?: {
                type?: string | null;
                organization_id?: string | null;
                include_assigned?: boolean;
            };
            header?: never;
            path: {
                incident_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AssignmentCandidate"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    mark_arrival_api_v1_assignments__assignment_id__arrival_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                assignment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignmentArrival"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    release_resource_api_v1_assignments__assignment_id__release_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                assignment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AssignmentRelease"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentDetail"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_resource_types_api_v1_resource_types_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceTypeResponse"][];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    list_resources_api_v1_resources_get: {
        parameters: {
            query?: {
                status?: components["schemas"]["ResourceStatus"][] | null;
                type?: string | null;
                organization_id?: string | null;
                municipality?: string | null;
                active?: boolean;
                q?: string | null;
                sort?: "code" | "status" | "-status_changed_at";
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourcePage"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    create_resource_api_v1_resources_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResourceCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_resource_api_v1_resources__resource_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resource_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    update_resource_api_v1_resources__resource_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resource_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResourceUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    change_resource_status_api_v1_resources__resource_id__status_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                resource_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResourceStatusChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ResourceResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    get_dashboard_summary_api_v1_dashboard_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DashboardSummary"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
