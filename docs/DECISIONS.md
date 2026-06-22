# DECISIONS.md

# Registro de decisiones técnicas

## Propósito

Este archivo registra decisiones que afectan al proyecto CEE Conecta.

Toda decisión debe tener:

- fecha;
- agente;
- contexto;
- decisión;
- justificación;
- impacto;
- estado.

---

## Estados permitidos

- `propuesta`
- `aprobada`
- `rechazada`
- `reemplazada`

---

## DEC-001 — Producto final sin agentes internos obligatorios

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Contexto

El curso exige usar una fábrica agéntica para desarrollar el proyecto, pero no obliga a que el producto final incorpore agentes de IA como funcionalidad visible.

### Decisión

CEE Conecta será una aplicación web tradicional. La fábrica agéntica será el proceso de desarrollo y generación de evidencia.

### Justificación

Esto evita sobredimensionar el producto y alinea el trabajo con la evaluación: entrada clara, refinamiento, planificación, agentes, workflows, arnés, validación, evidencia y cierre técnico.

### Impacto

El backend, frontend y base de datos no necesitan implementar lógica agéntica interna en el MVP.

---

## DEC-002 — Stack inicial

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

Usar:

- FastAPI para backend.
- React + Vite para frontend.
- PostgreSQL como base de datos.
- Pytest para pruebas backend y de fábrica.
- OpenAPI / Swagger para documentación API.

### Justificación

Es un stack rápido de desarrollar, claro para separar módulos y adecuado para una API REST.

### Impacto

Los agentes deben generar artefactos compatibles con este stack.

---

## DEC-003 — Autenticación institucional con Google

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

El sistema usará Google OAuth / OpenID Connect para autenticación con correo institucional.

### Justificación

Permite evitar almacenamiento de contraseñas y delegar identidad a Google.

### Impacto

La base de datos debe almacenar, como mínimo:

- identificador externo de Google;
- correo;
- nombre;
- rol;
- estado;
- último acceso.

---

## DEC-004 — Separación por hilos de trabajo

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

El trabajo se dividirá en hilos por agente:

- base de datos;
- backend;
- frontend;
- QA;
- seguridad;
- documentación.

### Justificación

Permite mantener foco, trazabilidad y responsabilidades claras.

### Impacto

Cada agente debe declarar su identidad y respetar el protocolo de trabajo definido en `docs/AGENT_PROTOCOL.md`.

---

## DEC-005 — Fuente de verdad documental

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

Los documentos de coordinación serán fuente de verdad:

- `docs/PROJECT_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/API_CONTRACT.md`
- `docs/DATABASE_MODEL.md`
- `docs/UI_MAP.md`
- `docs/HANDOFFS.md`

### Justificación

Evita inconsistencias entre agentes.

### Impacto

Todo cambio transversal debe actualizar documentos.

---

## DEC-006 - Modelo PostgreSQL inicial

**Fecha:** 2026-06-21
**Agente:** agent.database_designer
**Estado:** aprobada

### Contexto

El modelo inicial definido en `docs/DATABASE_MODEL.md` necesitaba convertirse en SQL ejecutable para habilitar el trabajo posterior de backend.

### Decision

Se crea `app/database/schema.sql` como esquema PostgreSQL base y `app/database/seed.sql` como seed inicial.

El esquema usa:

- `UUID` como clave primaria en todas las tablas principales.
- `gen_random_uuid()` mediante la extension `pgcrypto`.
- Tipos ENUM de PostgreSQL para estados estables de publicaciones, eventos, solicitudes, recursos, votaciones y otros flujos del dominio.
- `CHECK`, claves unicas, claves foraneas e indices para reglas de integridad iniciales.
- Indices parciales para evitar prestamos activos duplicados de un mismo recurso y respuestas duplicadas donde aplica.

### Justificacion

El uso de UUID facilita integracion con API REST y evita depender de secuencias expuestas. Los ENUM estabilizan estados compartidos entre base de datos, backend y documentacion. Las restricciones en base de datos reducen inconsistencias antes de implementar la capa de servicios.

### Impacto

El agente backend debe mapear los modelos y validaciones contra `schema.sql`, cargar `seed.sql` en ambientes locales y respetar los nombres de tablas, columnas y estados definidos.

---

## DEC-007 - Estructura base backend FastAPI

**Fecha:** 2026-06-21  
**Agente:** agent.backend_developer  
**Estado:** aprobada

### Contexto

El backend necesitaba una base ejecutable que respetara el contrato API, el
modelo PostgreSQL inicial y la separacion por agentes.

### Decision

Se crea `app/backend/` como paquete FastAPI con:

- aplicacion principal en `app/backend/main.py`;
- rutas versionadas bajo `/api/v1`;
- respuestas estandar `{ data, message, errors }`;
- manejadores globales de errores y validacion;
- configuracion con variables `CEE_*`;
- conexion PostgreSQL mediante SQLAlchemy async y driver `asyncpg`;
- health check de servicio y health check de base de datos separados;
- estructura de autenticacion Google OIDC y JWT local;
- dependencias `require_roles` y `require_permissions`;
- pruebas minimas en `tests/backend/`.

El JWT local conserva `role` como rol principal para compatibilidad y agrega
`roles` y `permissions` para autorizacion fina.

### Justificacion

La separacion por capas permite avanzar endpoints del MVP sin mezclar reglas de
dominio, transporte HTTP y persistencia. El health check de base de datos queda
separado para diagnosticar PostgreSQL sin impedir que el servicio exponga su
estado basico.

### Impacto

El frontend puede consumir endpoints bajo `/api/v1` y debe esperar respuestas
envueltas en el formato estandar. QA y seguridad deben revisar la validacion
OIDC real, el manejo de JWT y la autorizacion por roles/permisos antes de
habilitar flujos administrativos en produccion.

---

## DEC-008 - Gate de seguridad para endpoints administrativos

**Fecha:** 2026-06-21
**Agente:** agent.security_reviewer
**Estado:** aprobada

### Contexto

La revision de seguridad del backend base encontro que el JWT local conserva un
secreto por defecto conocido y que la autorizacion actual confia en claims del
token sin verificar sesion activa, revocacion, estado vigente del usuario ni
permisos actuales en base de datos.

### Decision

El backend no debe habilitar endpoints administrativos como listos para uso real
hasta implementar:

- validacion de configuracion segura por ambiente;
- secreto JWT obligatorio y no predeterminado fuera de desarrollo;
- verificacion de sesion activa, usuario activo y revocacion;
- permisos explicitos por endpoint administrativo;
- auditoria para toda accion administrativa.

Los endpoints publicos, health checks basicos, autenticacion y endpoints no
administrativos pueden continuar como base de desarrollo, siempre que no se
declaren listos para produccion.

### Justificacion

Los endpoints administrativos manejaran contenido publico, finanzas, documentos,
solicitudes, usuarios, roles y auditoria. Con la base actual, un secreto
predeterminado o una sesion no revocada podria derivar en acceso administrativo
indebido.

### Impacto

`agent.backend_developer` debe resolver los hallazgos criticos documentados en
`docs/SECURITY_REVIEW.md` antes de avanzar endpoints administrativos. El modelo
de datos actual ya incluye `sessions` y `audit_events`, por lo que no se requiere
cambio de base de datos para la primera mitigacion. Si backend necesita nuevos
campos o tablas para revocacion avanzada, debe dejar handoff a
`agent.database_designer`.

---

## DEC-009 - Autorizacion con sesion vigente y permisos actuales

**Fecha:** 2026-06-22  
**Agente:** agent.backend_developer  
**Estado:** aprobada

### Contexto

`agent.security_reviewer` bloqueo el avance de endpoints administrativos hasta
mitigar el secreto JWT predeterminado y la autorizacion basada solo en claims.

### Decision

El backend valida la configuracion de seguridad al crear la aplicacion: fuera de
ambientes `local`, `dev`, `development`, `test` o `testing`, `CEE_JWT_SECRET_KEY`
debe existir, no puede usar el valor por defecto y debe tener longitud minima de
32 caracteres.

Los JWT locales incluyen `sid`, identificador de la fila `sessions`. Cada request
protegida debe pasar por `require_auth()`, que decodifica el token y valida contra
base de datos:

- hash del token asociado a `sessions.session_token_hash`;
- `sessions.revoked_at IS NULL`;
- `sessions.expires_at` vigente;
- usuario `ACTIVE` y no eliminado;
- roles y permisos actuales desde `user_roles`, `roles`, `role_permissions` y
  `permissions`.

`require_permissions(...)` ya no acepta bypass por rol `ADMIN`: el permiso debe
estar vigente en base de datos. El seed actual otorga todos los permisos a
`ADMIN`, por lo que el rol mantiene acceso administrativo mientras sus permisos
sigan asignados.

Tambien se crea un servicio base de auditoria sobre `audit_events` para login
exitoso, login fallido, token invalido, acceso denegado y futuras acciones
administrativas.

### Justificacion

La revocacion operativa de sesiones, usuarios, roles o permisos debe tener efecto
sin esperar a que expire un JWT. La autorizacion administrativa debe depender del
estado vigente en base de datos y no de privilegios autocontenidos en el token.

### Impacto

Los endpoints protegidos requieren base de datos disponible. Las pruebas de
backend usan validadores fake para cubrir rutas sin depender de PostgreSQL real.
Todo endpoint administrativo futuro debe usar `require_permissions(...)` y
registrar acciones sensibles mediante `AuditService.record_administrative_action`.

---

## DEC-010 - Permisos administrativos para usuarios, roles y permisos

**Fecha:** 2026-06-22  
**Agente:** agent.backend_developer  
**Estado:** aprobada

### Contexto

Tras la revalidacion de seguridad, el backend puede comenzar endpoints
administrativos reales si no depende de permisos autocontenidos en el JWT, usa
`require_permissions(...)` y registra auditoria por accion administrativa.

### Decision

El modulo administrativo inicial queda protegido asi:

- `GET /api/v1/users`: requiere `users.manage`.
- `GET /api/v1/users/{user_id}`: requiere `users.manage`.
- `PATCH /api/v1/users/{user_id}/status`: requiere `users.manage`.
- `GET /api/v1/roles`: requiere `roles.manage`.
- `GET /api/v1/permissions`: requiere `roles.manage`.

El endpoint `PATCH /api/v1/users/{user_id}/status` registra auditoria
administrativa con `entity_type = "users"` y metadata con accion
`user.status.updated`, estado anterior y estado nuevo.

### Justificacion

El seed actual ya define permisos separados para administracion de usuarios y de
roles. Mantener esa separacion permite que QA y frontend validen capacidades
administrativas sin asumir que un rol por si mismo equivale a un permiso.

### Impacto

Los consumidores del API deben tratar `users.manage` y `roles.manage` como
capacidades separadas. Nuevos endpoints administrativos deben seguir usando
permisos explicitos y auditoria para acciones sensibles.

---

## DEC-011 - Permiso administrativo de contenido y archivado de noticias

**Fecha:** 2026-06-22  
**Agente:** agent.backend_developer  
**Estado:** aprobada

### Contexto

El modulo de noticias y comunicados requiere endpoints administrativos para
crear, editar, archivar y publicar contenido. El seed vigente no define permisos
separados `news.create`, `news.update`, `announcements.create` ni equivalentes;
define el permiso `content.publish` para crear y publicar noticias o
comunicados.

### Decision

El backend usara `content.publish` como permiso vigente para las acciones
administrativas del modulo de noticias y comunicados:

- `POST /api/v1/news`
- `PATCH /api/v1/news/{news_id}`
- `DELETE /api/v1/news/{news_id}`
- `POST /api/v1/news/{news_id}/publish`
- `POST /api/v1/announcements`
- `PATCH /api/v1/announcements/{announcement_id}`
- `POST /api/v1/announcements/{announcement_id}/publish`

El endpoint `DELETE /api/v1/news/{news_id}` realiza archivado logico cambiando
`news.status` a `ARCHIVED`; no borra fisicamente filas ni modifica el modelo de
datos.

Las acciones mutantes registran auditoria administrativa con `entity_type`
`news` o `announcements` y metadata de accion especifica.

### Justificacion

La decision respeta el seed existente y evita cambiar el modelo de datos o
crear permisos fuera de la fuente de verdad de base de datos. El estado
`ARCHIVED` ya existe para publicaciones y permite ocultar contenido del listado
publico sin perder trazabilidad.

### Impacto

QA y frontend deben tratar `content.publish` como capacidad administrativa de
contenido para el MVP. Si mas adelante se requieren permisos granulares por
modulo o accion, `agent.database_designer` debera ampliar el seed/modelo y
backend debera ajustar dependencias y contrato API.
