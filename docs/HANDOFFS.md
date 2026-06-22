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
**Estado:** pendiente

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
