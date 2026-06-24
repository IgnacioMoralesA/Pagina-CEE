# HANDOFFS.md

# Registro de handoffs entre agentes

## Propósito

Este archivo registra transferencias de información, dependencias o solicitudes entre agentes.

Cada handoff debe tener:

- origen;
- destino;
- contexto;
- entregables;
- acción requerida;
- estado.

---

## Estados permitidos

- `pendiente`
- `recibido`
- `en_proceso`
- `resuelto`
- `bloqueado`

---

## Handoff 001

**Fecha:** 2026-06-18  
**De:** agent.product_owner  
**Para:** agent.database_designer  
**Estado:** resuelto

### Contexto

Se definió el alcance inicial de CEE Conecta como plataforma web para gestión de Centro de Estudiantes.

### Entregables

- `docs/PROJECT_CONTEXT.md`
- módulos definidos;
- roles base;
- estados principales.

### Decisiones relevantes

- El producto final no necesita agentes internos.
- La fábrica agéntica se usa como proceso de desarrollo.
- Stack inicial: FastAPI, React, PostgreSQL.
- Login institucional mediante Google OAuth / OpenID Connect.

### Acción requerida

Diseñar el modelo de datos inicial con tablas, relaciones, claves, restricciones y seed base.

---

## Handoff 002

**Fecha:** 2026-06-18  
**De:** agent.product_owner  
**Para:** agent.backend_developer  
**Estado:** en_proceso  

### Contexto

El backend debe implementarse después de tener una primera versión del modelo de datos.

### Entregables

- `docs/PROJECT_CONTEXT.md`
- `docs/API_CONTRACT.md`
- `docs/DATABASE_MODEL.md`

### Acción requerida

Esperar el diseño de base de datos y luego implementar la API REST bajo `/api/v1`.

---

## Handoff 003

**Fecha:** 2026-06-18  
**De:** agent.product_owner  
**Para:** agent.frontend_developer  
**Estado:** pendiente  

### Contexto

El frontend debe consumir endpoints definidos por backend. No debe inventar rutas de API.

### Entregables

- `docs/PROJECT_CONTEXT.md`
- `docs/UI_MAP.md`
- `docs/API_CONTRACT.md`

### Acción requerida

Diseñar las rutas y pantallas iniciales, pero esperar el contrato API antes de integrar servicios reales.

---

## Handoff 004

**Fecha:** 2026-06-18  
**De:** agent.product_owner  
**Para:** agent.qa_engineer  
**Estado:** pendiente  

### Contexto

QA debe validar la fábrica, backend, frontend y trazabilidad del producto.

### Entregables

- `docs/PROJECT_CONTEXT.md`
- `docs/AGENT_PROTOCOL.md`
- checklist base.

### Acción requerida

Crear plan de pruebas y criterios de cobertura para los módulos prioritarios.

---

## Handoff 005

**Fecha:** 2026-06-21
**De:** agent.database_designer
**Para:** agent.backend_developer
**Estado:** en_proceso

### Contexto

Se implemento el primer modelo PostgreSQL ejecutable de CEE Conecta con tablas principales, claves primarias, claves foraneas, restricciones `CHECK`, indices, estados y seed inicial.

### Entregables

- `app/database/schema.sql`
- `app/database/seed.sql`
- `docs/DATABASE_MODEL.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-006 - Modelo PostgreSQL inicial`
- Las claves primarias usan `UUID` con `gen_random_uuid()`.
- Los estados compartidos se modelan como ENUM de PostgreSQL.
- `seed.sql` define los roles iniciales `STUDENT`, `BOARD_MEMBER`, `PRESIDENT`, `TREASURER`, `SECRETARY` y `ADMIN`.

### Accion requerida

Implementar modelos backend y contrato API respetando nombres de tablas, columnas, relaciones y estados definidos. El backend debe cargar `schema.sql` antes de `seed.sql` en ambientes locales y asegurar auditoria para acciones administrativas.

---

## Handoff 006

**Fecha:** 2026-06-21  
**De:** agent.backend_developer  
**Para:** agent.qa_engineer  
**Estado:** pendiente

### Contexto

Se implemento la estructura base del backend FastAPI con endpoints minimos,
respuestas estandar, errores globales, JWT local, roles/permisos y pruebas
unitarias iniciales.

### Entregables

- `app/backend/`
- `tests/backend/test_base_api.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-007 - Estructura base backend FastAPI`

### Accion requerida

Ampliar la estrategia de pruebas para integracion con PostgreSQL, autenticacion
Google configurada, autorizacion por permisos y endpoints del MVP.

---

## Handoff 007

**Fecha:** 2026-06-21  
**De:** agent.backend_developer  
**Para:** agent.security_reviewer  
**Estado:** resuelto

### Contexto

La base de autenticacion usa Google OIDC mediante `tokeninfo`, restringe dominio
institucional si se configura `CEE_INSTITUTIONAL_EMAIL_DOMAIN`, emite JWT local
con roles/permisos y no almacena contrasenas.

### Entregables

- `app/backend/auth/`
- `app/backend/core/errors.py`
- `app/backend/api/v1/auth.py`
- `docs/API_CONTRACT.md`

### Decisiones relevantes

- `DEC-003 - Autenticacion institucional con Google`
- `DEC-007 - Estructura base backend FastAPI`

### Accion requerida

Revisar estrategia OIDC/JWT, expiracion, manejo de errores, permisos y
requisitos de seguridad antes de abrir endpoints administrativos.

---

## Handoff 008

**Fecha:** 2026-06-21  
**De:** agent.backend_developer  
**Para:** agent.frontend_developer  
**Estado:** pendiente

### Contexto

El backend ya expone endpoints base versionados y el contrato documenta la
respuesta estandar esperada por el frontend.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/health.py`
- `app/backend/api/v1/auth.py`
- `app/backend/api/v1/users.py`

### Decisiones relevantes

- `DEC-007 - Estructura base backend FastAPI`

### Accion requerida

Consumir solo endpoints documentados bajo `/api/v1`, respetar el envelope
`{ data, message, errors }` y usar `Authorization: Bearer <access_token>` para
`GET /users/me`.

---

## Handoff 009

**Fecha:** 2026-06-21
**De:** agent.security_reviewer
**Para:** agent.backend_developer
**Estado:** resuelto

### Contexto

Se reviso la base de seguridad FastAPI. La estructura es adecuada para desarrollo,
pero no esta lista para endpoints administrativos porque el JWT puede usar un
secreto por defecto y la autorizacion actual no valida sesion activa, revocacion,
estado vigente del usuario ni permisos actuales contra base de datos.

### Entregables

- `docs/SECURITY_REVIEW.md`
- `docs/DECISIONS.md`
- `tests/backend/test_security_base.py`

### Decisiones relevantes

- `DEC-003 - Autenticacion institucional con Google`
- `DEC-007 - Estructura base backend FastAPI`
- `DEC-008 - Gate de seguridad para endpoints administrativos`

### Accion requerida

Antes de implementar endpoints administrativos:

- agregar validacion de configuracion segura por ambiente;
- exigir `CEE_JWT_SECRET_KEY` no predeterminado fuera de desarrollo;
- vincular JWT con sesion activa y rechazar sesiones revocadas o expiradas;
- comprobar `users.status = ACTIVE` y permisos vigentes para endpoints sensibles;
- endurecer Google OIDC con verificacion local/JWKS, issuer, expiracion y `hd` si aplica;
- agregar rate limiting y auditoria completa de fallos de login;
- ocultar detalles internos en errores 500 y health de base de datos;
- aplicar `require_permissions(...)` con permisos explicitos en cada endpoint administrativo;
- escribir `audit_events` para toda accion administrativa;
- agregar pruebas negativas y positivas por rol/permiso.

Si alguna mitigacion requiere nuevos campos o tablas, dejar handoff a
`agent.database_designer` antes de cambiar el modelo de datos.

---

## Handoff 010

**Fecha:** 2026-06-22
**De:** agent.backend_developer
**Para:** agent.security_reviewer
**Estado:** resuelto

### Contexto

Se implemento el refactor de seguridad solicitado antes de avanzar endpoints
administrativos. El backend ahora bloquea secretos JWT inseguros fuera de
desarrollo, emite JWT con `sid`, valida sesion activa y permisos vigentes contra
base de datos, restringe `/api/v1/health/database`, sanitiza errores internos y
agrega servicio base de auditoria.

### Entregables

- `app/backend/core/config.py`
- `app/backend/main.py`
- `app/backend/auth/jwt.py`
- `app/backend/auth/context.py`
- `app/backend/auth/dependencies.py`
- `app/backend/auth/service.py`
- `app/backend/audit/service.py`
- `app/backend/api/v1/health.py`
- `tests/backend/test_security_base.py`
- `tests/backend/test_base_api.py`
- `docs/SECURITY_REVIEW.md`
- `docs/DECISIONS.md`
- `docs/API_CONTRACT.md`

### Decisiones relevantes

- `DEC-008 - Gate de seguridad para endpoints administrativos`
- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`

### Accion requerida

Revalidar los hallazgos `SR-CRIT-001` y `SR-CRIT-002`, confirmar que los riesgos
criticos quedan mitigados y aprobar o rechazar el comienzo de endpoints
administrativos reales bajo `require_permissions(...)` y auditoria obligatoria.

### Resultado de revalidacion

`agent.security_reviewer` confirma que `SR-CRIT-001` y `SR-CRIT-002` estan
resueltos. El backend puede comenzar endpoints administrativos reales bajo
`require_permissions(...)`, permisos vigentes contra base de datos y auditoria
obligatoria por accion administrativa.

---

## Handoff 011

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.qa_engineer  
**Estado:** resuelto

### Contexto

Se implemento el modulo backend inicial de usuarios, roles y permisos como base
para endpoints administrativos reales. Las rutas usan `require_permissions(...)`,
validan sesion activa y usuario `ACTIVE` mediante la capa de autenticacion
existente, y el cambio de estado de usuarios registra auditoria administrativa.

### Entregables

- `app/backend/api/v1/users.py`
- `app/backend/api/v1/access_control.py`
- `app/backend/users/`
- `tests/backend/test_users_module.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-010 - Permisos administrativos para usuarios, roles y permisos`

### Accion requerida

Validar los endpoints administrativos iniciales con pruebas de contrato,
autorizacion por permisos, usuario inactivo, sesion revocada/expirada y auditoria
de `PATCH /api/v1/users/{user_id}/status`.

---

## Handoff 012

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.frontend_developer  
**Estado:** pendiente

### Contexto

El backend ya formalizo endpoints reales para usuario actual, administracion
basica de usuarios y consulta de roles/permisos. Todos responden con el envelope
estandar `{ data, message, errors }` y requieren bearer token salvo errores de
autenticacion.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/users.py`
- `app/backend/api/v1/access_control.py`

### Decisiones relevantes

- `DEC-010 - Permisos administrativos para usuarios, roles y permisos`

### Accion requerida

Integrar solo las rutas documentadas:

- `GET /api/v1/users/me`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}/status`
- `GET /api/v1/roles`
- `GET /api/v1/permissions`

Mostrar u ocultar acciones administrativas en UI segun permisos vigentes
devueltos por `/api/v1/users/me`, sin asumir privilegios por nombre de rol.

---

## Handoff 013

**Fecha:** 2026-06-22  
**De:** agent.qa_engineer  
**Para:** agent.backend_developer  
**Estado:** resuelto

### Contexto

QA valido el modulo backend inicial de usuarios, roles y permisos contra el
contrato API, las reglas de seguridad vigentes y la suite automatizada. Se
agrego cobertura de rutas para permisos administrativos, rechazo de sesiones
revocadas/expiradas, usuario inactivo, ausencia de bypass por rol `ADMIN` y
formato estandar de respuesta.

### Entregables

- `docs/QA_REPORT.md`
- `docs/CHECKLIST_VALIDACION.md`
- `tests/backend/test_users_module.py`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-010 - Permisos administrativos para usuarios, roles y permisos`

### Accion requerida

Backend puede avanzar al modulo de noticias/comunicados manteniendo estas
condiciones:

- usar `require_permissions(...)` con permisos explicitos por endpoint
  administrativo;
- validar sesion vigente, usuario `ACTIVE` y permisos actuales contra base de
  datos;
- registrar auditoria para acciones administrativas mutantes;
- agregar pruebas negativas por permisos faltantes, sesion invalida y usuario
  inactivo.

Observaciones no bloqueantes: agregar prueba de integracion con PostgreSQL real
para confirmar persistencia en `audit_events` y definir si un PATCH idempotente
de estado tambien debe auditarse.

### Resultado

`agent.backend_developer` implemento el modulo de noticias/comunicados bajo las
condiciones indicadas: permiso vigente `content.publish`, auditoria
administrativa en acciones mutantes y pruebas negativas de autenticacion y
autorizacion.

---

## Handoff 014

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.qa_engineer  
**Estado:** resuelto

### Contexto

Se implemento el modulo backend de noticias y comunicados. Los endpoints
publicos listan solo contenido `PUBLISHED` por defecto; borradores y archivados
requieren permiso vigente `content.publish` cuando se consultan mediante filtros
administrativos. Las acciones mutantes de noticias y comunicados registran
auditoria administrativa.

### Entregables

- `app/backend/api/v1/news.py`
- `app/backend/api/v1/announcements.py`
- `app/backend/content/`
- `tests/backend/test_content_module.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-011 - Permiso administrativo de contenido y archivado de noticias`

### Accion requerida

Validar contrato, paginacion, filtros publicos/administrativos, ausencia de
exposicion de borradores, permisos `content.publish`, respuestas 401/403,
auditoria de create/update/archive/publish y que `DELETE /news/{news_id}` no
realice borrado fisico.

---

## Handoff 015

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.frontend_developer  
**Estado:** pendiente

### Contexto

El backend ya expone endpoints reales para noticias y comunicados usando el
envelope estandar `{ data, message, errors }`. Las lecturas publicas solo
devuelven contenido publicado por defecto; las acciones administrativas requieren
bearer token con permiso vigente `content.publish`.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/news.py`
- `app/backend/api/v1/announcements.py`

### Decisiones relevantes

- `DEC-011 - Permiso administrativo de contenido y archivado de noticias`

### Accion requerida

Integrar solo las rutas documentadas:

- `GET /api/v1/news`
- `GET /api/v1/news/{news_id}`
- `POST /api/v1/news`
- `PATCH /api/v1/news/{news_id}`
- `DELETE /api/v1/news/{news_id}`
- `POST /api/v1/news/{news_id}/publish`
- `GET /api/v1/announcements`
- `POST /api/v1/announcements`
- `PATCH /api/v1/announcements/{announcement_id}`
- `POST /api/v1/announcements/{announcement_id}/publish`

Mostrar acciones de administracion de contenido solo cuando `/api/v1/users/me`
incluya `content.publish`.

---

## Handoff 016

**Fecha:** 2026-06-22  
**De:** agent.qa_engineer  
**Para:** agent.backend_developer  
**Estado:** resuelto

### Contexto

QA valido el modulo backend de noticias y comunicados contra contrato, seguridad,
auditoria, reglas de negocio y pruebas automatizadas. Se agrego cobertura para
filtros publicos, detalle publico de contenido no publicado, mutaciones sin
sesion, mutaciones sin permiso, flujos con permiso, contenido vacio, archivado
logico, publicacion con `published_at` y auditoria administrativa.

### Entregables

- `docs/QA_REPORT.md`
- `docs/CHECKLIST_VALIDACION.md`
- `tests/backend/test_content_module.py`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-011 - Permiso administrativo de contenido y archivado de noticias`

### Accion requerida

Backend puede avanzar al modulo de eventos manteniendo estas condiciones:

- usar `require_permissions(...)` con permisos explicitos por endpoint
  administrativo;
- filtrar lecturas publicas por estados publicables;
- validar contenido vacio y transiciones de estado antes de publicar;
- registrar auditoria para acciones administrativas mutantes;
- agregar pruebas de `401`, `403`, publicacion, estados no publicos y envelope
  `{ data, message, errors }`.

Observaciones no bloqueantes antes de integracion estricta: alinear la respuesta
de `DELETE /api/v1/news/{news_id}` con el ejemplo contractual `{ id, status }`
o actualizar el contrato para documentar `NewsResponse` completo; agregar prueba
de integracion con PostgreSQL real para confirmar persistencia en `audit_events`;
definir si mutaciones idempotentes deben registrarse en auditoria.

### Resultado

`agent.backend_developer` implemento el modulo de eventos, inscripciones y
asistencia bajo las condiciones indicadas: permiso `events.manage` para
administracion, lecturas publicas filtradas por eventos publicados/proximos,
inscripciones autenticadas y auditoria en acciones administrativas mutantes.

---

## Handoff 017

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.qa_engineer  
**Estado:** resuelto

### Contexto

Se implemento el modulo backend de eventos, inscripciones y asistencia. Los
eventos publicos listan `PUBLISHED` proximos por defecto; estados no publicos
requieren `events.manage`. Las acciones administrativas de create/update/publish/
cancel/finish/attendance usan `require_permissions(...)` y registran auditoria.
Las inscripciones requieren usuario autenticado, evento publicado, no duplicidad
y capacidad disponible.

### Entregables

- `app/backend/api/v1/events.py`
- `app/backend/events/`
- `tests/backend/test_events_module.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-012 - Publicacion, cancelacion e inscripciones de eventos`

### Accion requerida

Validar contrato, paginacion, filtros publicos/administrativos, estados no
publicos, fechas, capacidad, duplicidad de inscripciones, cancelacion de
inscripcion propia, asistencia solo para inscritos, respuestas 401/403 y
auditoria de acciones administrativas.

---

## Handoff 018

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.frontend_developer  
**Estado:** pendiente

### Contexto

El backend ya expone endpoints reales para eventos, inscripciones y asistencia
con envelope `{ data, message, errors }`. Las lecturas publicas muestran eventos
`PUBLISHED` proximos; las acciones administrativas requieren bearer token con
permiso vigente `events.manage`.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/events.py`

### Decisiones relevantes

- `DEC-012 - Publicacion, cancelacion e inscripciones de eventos`

### Accion requerida

Integrar solo las rutas documentadas:

- `GET /api/v1/events`
- `GET /api/v1/events/{event_id}`
- `POST /api/v1/events`
- `PATCH /api/v1/events/{event_id}`
- `POST /api/v1/events/{event_id}/publish`
- `POST /api/v1/events/{event_id}/cancel`
- `POST /api/v1/events/{event_id}/finish`
- `POST /api/v1/events/{event_id}/register`
- `DELETE /api/v1/events/{event_id}/registration`
- `POST /api/v1/events/{event_id}/attendance`

Mostrar administracion y asistencia solo si `/api/v1/users/me` incluye
`events.manage`. Permitir inscripcion con usuario autenticado cuando el evento
este publicado y tenga cupos disponibles.

---

## Handoff 019

**Fecha:** 2026-06-22  
**De:** agent.qa_engineer  
**Para:** agent.backend_developer  
**Estado:** resuelto

### Contexto

QA valido el modulo backend de eventos, inscripciones y asistencia contra
contrato, reglas de negocio, permisos, auditoria, estados y pruebas
automatizadas. Se agrego cobertura para lecturas publicas, estados no publicos,
acciones administrativas sin sesion, acciones administrativas sin permiso,
flujos administrativos con `events.manage`, fechas invalidas, capacidad,
duplicidad de inscripciones, inscripcion autenticada sin permiso administrativo,
cancelacion de inscripcion propia, aislamiento frente a otras inscripciones y
asistencia solo con inscripcion previa.

### Entregables

- `docs/QA_REPORT.md`
- `docs/CHECKLIST_VALIDACION.md`
- `tests/backend/test_events_module.py`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-012 - Publicacion, cancelacion e inscripciones de eventos`

### Accion requerida

Backend puede avanzar al modulo de solicitudes estudiantiles manteniendo estas
condiciones:

- usar `require_permissions(...)` con permisos explicitos por endpoint
  administrativo;
- validar estado actual y transiciones permitidas antes de mutar;
- registrar auditoria para acciones administrativas mutantes;
- mantener lecturas publicas filtradas por estados publicables;
- agregar pruebas de `401`, `403`, reglas de negocio, estados invalidos y
  envelope `{ data, message, errors }`.

Observaciones no bloqueantes: agregar prueba de integracion con PostgreSQL real
para confirmar persistencia en `audit_events`; definir si acciones
administrativas idempotentes deben registrar auditoria nueva.

### Resultado

`agent.backend_developer` implemento el modulo de solicitudes estudiantiles bajo
las condiciones indicadas: permisos `requests.create` y `requests.manage`,
visibilidad por propietario o permiso administrativo, historial de estados,
comentarios y auditoria en acciones administrativas mutantes.

---

## Handoff 020

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.qa_engineer  
**Estado:** resuelto

### Contexto

Se implemento el modulo backend de solicitudes estudiantiles. Los estudiantes
pueden crear solicitudes con `requests.create`, listar/ver sus propias
solicitudes, editar solicitudes propias en `SUBMITTED` u `OBSERVED` y comentar
solicitudes propias. Usuarios con `requests.manage` pueden listar todas,
filtrar, asignar, observar, aprobar, rechazar, cerrar y crear comentarios
internos. Las transiciones registran `request_status_history` y las acciones
administrativas mutantes registran auditoria.

### Entregables

- `app/backend/api/v1/requests.py`
- `app/backend/student_requests/`
- `tests/backend/test_requests_module.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-013 - Flujo inicial de solicitudes estudiantiles`

### Accion requerida

Validar contrato, visibilidad por propietario, permisos `requests.create` y
`requests.manage`, paginacion, filtros administrativos, edicion por estado,
transiciones invalidas, motivos obligatorios, comentarios, historial de estado,
respuestas 401/403 y auditoria administrativa.

### Resultado

`agent.qa_engineer` valido el modulo de solicitudes estudiantiles contra
contrato, permisos, visibilidad, transiciones, historial, comentarios, auditoria
y pruebas automatizadas. Se agrego cobertura para `requests.create`, filtros
administrativos, edicion en `OBSERVED`, bloqueo de estados terminales, campos
administrativos, rutas administrativas sin sesion o sin permiso, motivos
obligatorios, aprobacion de solicitud rechazada, categoria invalida y permisos
de comentarios internos.

---

## Handoff 021

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.frontend_developer  
**Estado:** pendiente

### Contexto

El backend ya expone endpoints reales para solicitudes estudiantiles con envelope
`{ data, message, errors }`. La lectura por defecto muestra solicitudes propias;
la vista global y acciones de gestion requieren `requests.manage`.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/requests.py`

### Decisiones relevantes

- `DEC-013 - Flujo inicial de solicitudes estudiantiles`

### Accion requerida

Integrar solo las rutas documentadas:

- `GET /api/v1/requests`
- `POST /api/v1/requests`
- `GET /api/v1/requests/{request_id}`
- `PATCH /api/v1/requests/{request_id}`
- `POST /api/v1/requests/{request_id}/assign`
- `POST /api/v1/requests/{request_id}/observe`
- `POST /api/v1/requests/{request_id}/approve`
- `POST /api/v1/requests/{request_id}/reject`
- `POST /api/v1/requests/{request_id}/close`
- `POST /api/v1/requests/{request_id}/comments`

Mostrar gestion administrativa solo si `/api/v1/users/me` incluye
`requests.manage`. Mantener adjuntos de solicitudes fuera de UI real hasta que
backend implemente controles de archivos.

---

## Handoff 022

**Fecha:** 2026-06-22  
**De:** agent.qa_engineer  
**Para:** agent.backend_developer  
**Estado:** pendiente

### Contexto

QA valido el modulo backend de solicitudes estudiantiles. La suite backend queda
verde con cobertura ampliada y sin hallazgos criticos ni medios bloqueantes.
El contrato mantiene `POST /requests/{id}/attachments` como pendiente para el
modulo de documentos/archivos.

### Entregables

- `docs/QA_REPORT.md`
- `docs/CHECKLIST_VALIDACION.md`
- `tests/backend/test_requests_module.py`
- `docs/HANDOFFS.md`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-013 - Flujo inicial de solicitudes estudiantiles`

### Accion requerida

Backend puede avanzar al modulo de documentos/archivos manteniendo estas
condiciones:

- usar `require_permissions(...)` con permisos explicitos;
- validar sesion vigente, usuario `ACTIVE` y permisos actuales contra base de
  datos;
- registrar auditoria para acciones administrativas mutantes;
- no cambiar el modelo de datos sin handoff a `agent.database_designer`;
- antes de implementar adjuntos, definir controles de archivos: MIME permitido,
  tamano maximo, nombre seguro, almacenamiento privado y descarga autorizada;
- agregar pruebas de `401`, `403`, validacion de archivos, visibilidad y
  envelope `{ data, message, errors }`.

Finanzas basicas queda desbloqueada como modulo posterior del MVP si se
prioriza, pero el siguiente agente recomendado es `agent.backend_developer` para
documentos/archivos por la dependencia directa de adjuntos de solicitudes.

---

## Handoff 023

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.security_reviewer  
**Estado:** resuelto

### Contexto

Se implemento el modulo backend de documentos, archivos y adjuntos de
solicitudes. Incluye validacion de MIME/extension, limite de 10 MB, nombres
publicos sanitizados, clave interna UUID en `file_url`, calculo SHA-256,
descargas autorizadas y bloqueo de path traversal.

El backend usa un parser multipart local basado en la libreria estandar `email`
porque `python-multipart` no esta instalado en el entorno actual.

### Entregables

- `app/backend/files/`
- `app/backend/documents/`
- `app/backend/api/v1/documents.py`
- `app/backend/api/v1/requests.py`
- `tests/backend/test_documents_module.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-009 - Autorizacion con sesion vigente y permisos actuales`
- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`

### Accion requerida

Revalidar controles de subida y descarga:

- MIME y extension permitidos;
- limite de tamano;
- rechazo de archivo vacio;
- sanitizacion de nombre;
- resolucion segura de rutas;
- no exposicion de `file_url` ni rutas fisicas;
- visibilidad publica/privada;
- autorizacion de adjuntos por solicitante o `requests.manage`;
- auditoria de acciones administrativas;
- parser multipart local.

### Resultado

Revision completada el 2026-06-24. No quedan riesgos criticos abiertos. Se
aplicaron lectura multipart acotada, validacion basica de firma/contenido,
correccion del archivado logico en repositorio de base de datos y pruebas de
regresion. El modulo puede pasar a QA funcional con los riesgos medios
registrados en `docs/SECURITY_REVIEW.md`.

---

## Handoff 024

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.qa_engineer  
**Estado:** resuelto

### Contexto

El modulo backend de documentos/archivos quedo implementado con pruebas
automatizadas iniciales. La suite backend paso localmente con 148 pruebas.

### Entregables

- `tests/backend/test_documents_module.py`
- `app/backend/documents/`
- `app/backend/files/`
- `app/backend/api/v1/documents.py`
- `app/backend/api/v1/requests.py`
- `docs/API_CONTRACT.md`

### Decisiones relevantes

- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`

### Accion requerida

Validar el modulo contra contrato y criterios del avance:

- documentos publicos versus privados;
- filtros administrativos;
- `documents.manage` en endpoints administrativos;
- hash SHA-256;
- auditoria de creacion, actualizacion, eliminacion logica y adjuntos
  administrativos;
- errores `401`/`403`/`409`/`413`/`415`;
- envelope `{ data, message, errors }` en respuestas JSON;
- descargas binarias sin rutas internas.

### Resultado

QA funcional completada el 2026-06-24. Se agregaron 24 pruebas y las suites
cerraron con `174 passed` en backend y `178 passed` globales. No se detectaron
defectos funcionales bloqueantes. El modulo puede avanzar a finanzas basicas,
manteniendo el hardening de produccion de `Handoff 027`.

---

## Handoff 025

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.frontend_developer  
**Estado:** pendiente

### Contexto

El backend ya expone endpoints reales para documentos generales y adjuntos de
solicitudes. Las subidas usan `multipart/form-data` y las descargas se consumen
desde endpoints `/download`.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/documents.py`
- `app/backend/api/v1/requests.py`

### Decisiones relevantes

- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`

### Accion requerida

Integrar solo las rutas documentadas:

- `GET /api/v1/documents`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/download`
- `PATCH /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/requests/{request_id}/attachments`
- `GET /api/v1/requests/{request_id}/attachments`
- `GET /api/v1/requests/{request_id}/attachments/{attachment_id}/download`

Mostrar gestion documental solo si `/api/v1/users/me` incluye
`documents.manage`. Mostrar adjuntos de solicitudes al solicitante y a usuarios
con `requests.manage`. No usar ni esperar rutas internas de archivos.

---

## Handoff 026

**Fecha:** 2026-06-22  
**De:** agent.backend_developer  
**Para:** agent.database_designer  
**Estado:** pendiente

### Contexto

El modulo de archivos se implemento sin cambiar el modelo de datos. Para
cumplir SHA-256 en adjuntos de solicitudes, el backend guarda el hash en
metadatos locales sidecar porque `request_attachments` no tiene columna de hash.
La tabla tampoco tiene `deleted_at`.

### Entregables

- `app/database/schema.sql`
- `app/backend/documents/service.py`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`

### Accion requerida

Evaluar en una fase posterior si corresponde agregar columnas o una tabla comun
de archivos para persistir `sha256`, `storage_key`, metadatos de almacenamiento
y eliminacion logica de adjuntos. No es bloqueante para QA del modulo actual.

---

## Handoff 027

**Fecha:** 2026-06-24
**De:** agent.security_reviewer
**Para:** agent.backend_developer
**Estado:** pendiente

### Contexto

La revision especifica del modulo de archivos cerro los bypasses inmediatos de
tamano y contenido, pero identifico hardening de produccion que excede una
correccion pequena y localizada.

### Entregables

- `docs/SECURITY_REVIEW.md`
- `app/backend/files/multipart.py`
- `app/backend/files/storage.py`
- `tests/backend/test_documents_module.py`

### Decisiones relevantes

- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`
- `DEC-015 - Validacion de contenido y lectura multipart acotada`

### Accion requerida

- reemplazar el parser local por una libreria multipart mantenida;
- configurar limites equivalentes en proxy y servidor;
- incorporar cuarentena y escaneo antimalware para archivos no confiables;
- definir rechazo o neutralizacion de CSV injection;
- validar en produccion que `CEE_FILE_STORAGE_PATH` sea privado, escribible y
  no servido como contenido estatico;
- validar que `CEE_MAX_UPLOAD_SIZE_BYTES` sea positivo y razonable;
- definir verificacion de integridad y limpieza de archivos huerfanos;
- coordinar con `Handoff 026` si la solucion requiere cambios de modelo.

Estos puntos no bloquean QA funcional, pero los controles de malware, CSV y
aislamiento del almacenamiento deben resolverse antes de produccion.

---

## Handoff 028

**Fecha:** 2026-06-24
**De:** agent.security_reviewer
**Para:** agent.qa_engineer
**Estado:** resuelto

### Contexto

El modulo de documentos, archivos y adjuntos supero la revision de seguridad
sin riesgos criticos abiertos. Las correcciones agregadas cuentan con pruebas
automatizadas y el modulo queda apto con observaciones para QA funcional.

### Entregables

- `docs/SECURITY_REVIEW.md`
- `tests/backend/test_documents_module.py`
- `app/backend/files/`
- `app/backend/documents/`

### Decisiones relevantes

- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`
- `DEC-015 - Validacion de contenido y lectura multipart acotada`

### Accion requerida

Ejecutar el alcance de `Handoff 024` e incluir:

- archivos vacios, sobredimensionados, con firma invalida o MIME inconsistente;
- request multipart sin `Content-Length`;
- documento privado sin `documents.manage`;
- adjunto solicitado por usuario que no es dueno y no tiene
  `requests.manage`;
- descarga binaria con nombre sanitizado y sin rutas internas;
- archivado logico y auditoria administrativa.

Baseline de seguridad entregada:

- `pytest -q tests/backend --basetemp .pytest-tmp`: 150 passed;
- `pytest -q --basetemp .pytest-tmp`: 154 passed.

### Resultado

QA confirmo los controles de firma, tamano, permisos, visibilidad, nombre
seguro, UUID interno, SHA-256, archivado logico, auditoria y envelope. Los seis
formatos permitidos fueron aceptados con contenido valido. Resultado final:
`174 passed` backend y `178 passed` globales. Los riesgos medios de seguridad se
mantienen sin cambios y no bloquean el avance funcional.

---

## Handoff 029

**Fecha:** 2026-06-24
**De:** agent.qa_engineer
**Para:** agent.backend_developer
**Estado:** resuelto

### Contexto

El modulo de documentos, archivos y adjuntos de solicitudes completo QA
funcional sin hallazgos criticos ni defectos medios bloqueantes. Se amplio la
cobertura automatizada de 150 a 174 pruebas backend y la suite global cerro con
178 pruebas.

La revision de seguridad previa sigue considerando no aptas para produccion las
cargas no confiables hasta resolver antimalware, CSV injection y aislamiento
estricto del almacenamiento.

### Entregables

- `docs/QA_REPORT.md`
- `docs/CHECKLIST_VALIDACION.md`
- `tests/backend/test_documents_module.py`
- `docs/SECURITY_REVIEW.md`

### Decisiones relevantes

- `DEC-014 - Politica inicial de documentos, archivos y adjuntos`
- `DEC-015 - Validacion de contenido y lectura multipart acotada`

### Accion requerida

Puede comenzar el modulo de finanzas basicas manteniendo permisos vigentes,
auditoria administrativa y envelope estandar.

En paralelo o antes de produccion, completar `Handoff 027`:

- cuarentena y escaneo antimalware;
- mitigacion de CSV injection;
- parser multipart mantenido y limites equivalentes en proxy;
- validacion de almacenamiento privado;
- verificacion de integridad y limpieza de archivos huerfanos.

---

## Handoff 030

**Fecha:** 2026-06-24
**De:** agent.backend_developer
**Para:** agent.qa_engineer
**Estado:** pendiente

### Contexto

Se implemento el modulo de finanzas basicas con presupuestos, ingresos, gastos,
aprobacion y resumen. Las mutaciones requieren `finances.manage` y registran
auditoria administrativa.

### Entregables

- `app/backend/finances/`
- `app/backend/api/v1/finances.py`
- `app/backend/api/router.py`
- `tests/backend/test_finances_module.py`
- `docs/API_CONTRACT.md`
- `docs/DECISIONS.md`

### Decisiones relevantes

- `DEC-016 - Visibilidad, estados y comprobantes de finanzas basicas`

### Accion requerida

Validar:

- respuestas `401` y `403`;
- visibilidad publica y filtros administrativos;
- montos positivos, fechas y referencias;
- auditoria de creacion, actualizacion y aprobacion;
- bloqueo de edicion y doble aprobacion;
- calculo publico y operativo del resumen;
- envelope `{ data, message, errors }`.

Baseline entregada:

- `pytest -q tests/backend --basetemp .pytest-tmp`: `204 passed, 1 warning`.
- `pytest -q --basetemp .pytest-tmp`: `208 passed, 1 warning`.

El hardening de archivos de `Handoff 027` sigue pendiente; finanzas solo
referencia documentos existentes y no agrega nuevas cargas.

---

## Handoff 031

**Fecha:** 2026-06-24
**De:** agent.backend_developer
**Para:** agent.frontend_developer
**Estado:** pendiente

### Contexto

El backend expone finanzas bajo `/api/v1/finances` con envelope estandar. La
administracion debe mostrarse solo cuando `/api/v1/users/me` incluya
`finances.manage`.

### Entregables

- `docs/API_CONTRACT.md`
- `app/backend/api/v1/finances.py`
- `app/backend/finances/schemas.py`

### Decisiones relevantes

- `DEC-016 - Visibilidad, estados y comprobantes de finanzas basicas`

### Accion requerida

Integrar:

- `GET/POST /api/v1/finances/budgets`;
- `GET/PATCH /api/v1/finances/budgets/{budget_id}`;
- `GET/POST /api/v1/finances/income`;
- `GET/POST /api/v1/finances/expenses`;
- `PATCH /api/v1/finances/expenses/{expense_id}`;
- `POST /api/v1/finances/expenses/{expense_id}/approve`;
- `GET /api/v1/finances/summary`.

Tratar montos como decimales. Para crear o cambiar un gasto, enviar
`receipt_document_id`; usar `receipt_download_url` para descargar y respetar
las respuestas de autorizacion del modulo documental.
