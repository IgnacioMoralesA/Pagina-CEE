# QA_REPORT.md

# Reporte QA - usuarios, roles y permisos

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_auth_users_permissions  
**Alcance:** `app/backend/`, `tests/backend/`, contrato API y documentos de coordinacion.

---

## Resultado ejecutivo

El modulo backend de usuarios, roles y permisos queda validado para avanzar al
modulo de noticias/comunicados.

La revision confirma que:

- `GET /api/v1/users/me` requiere bearer token valido.
- Los endpoints administrativos usan `require_permissions(...)`.
- `GET /api/v1/users` y `GET /api/v1/users/{user_id}` requieren `users.manage`.
- `PATCH /api/v1/users/{user_id}/status` requiere `users.manage`.
- `GET /api/v1/roles` y `GET /api/v1/permissions` requieren `roles.manage`.
- Un usuario sin permiso vigente recibe `403`.
- Una sesion inexistente, revocada o expirada recibe `401`.
- Un usuario inactivo recibe `403`.
- No existe bypass por rol `ADMIN` sin permiso explicito.
- Las respuestas revisadas respetan el envelope `{ data, message, errors }`.
- El cambio efectivo de estado de usuario registra auditoria administrativa.

---

## Matriz de validacion

| Criterio | Resultado | Evidencia |
| --- | --- | --- |
| Contrato de endpoints coincide con `docs/API_CONTRACT.md` | Aprobado | `app/backend/api/v1/users.py`, `app/backend/api/v1/access_control.py`, `tests/backend/test_users_module.py` |
| `/users/me` requiere autenticacion valida | Aprobado | `test_users_me_requires_bearer_token`, `test_authenticated_user_can_read_me` |
| Endpoints administrativos exigen permisos correctos | Aprobado | pruebas de `users.manage` y `roles.manage` |
| Usuario sin permiso recibe `403` | Aprobado | `test_user_without_permission_receives_403` |
| Usuario sin sesion activa recibe `401` | Aprobado | `test_user_without_active_session_receives_401` |
| Sesion revocada o expirada no puede operar | Aprobado | `test_auth_context_rejects_invalid_current_session_state`, `test_administrative_endpoints_reject_revoked_or_expired_session` |
| Usuario inactivo no puede operar | Aprobado | `test_inactive_user_cannot_operate` |
| `PATCH /users/{user_id}/status` genera auditoria | Aprobado para cambio efectivo | `test_status_change_generates_administrative_audit` |
| No hay bypass por rol `ADMIN` sin permiso | Aprobado | `test_admin_role_without_users_manage_permission_receives_403`, `test_permission_dependency_requires_current_permission_even_for_admin` |
| Respuestas respetan formato estandar | Aprobado | asserts de `data`, `message`, `errors` en rutas revisadas |

---

## Pruebas ejecutadas

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado inicial antes de ampliar cobertura: `31 passed, 1 warning`.

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado despues de ampliar cobertura: `39 passed, 1 warning`.

```bash
pytest -q --basetemp .pytest-tmp
```

Resultado global del repositorio: `43 passed, 1 warning`.

---

## Hallazgos criticos

No se detectaron hallazgos criticos en el modulo revisado.

---

## Hallazgos medios

No se detectaron hallazgos medios bloqueantes.

---

## Hallazgos menores

### QA-MIN-001 - Auditoria persistida no se valida contra PostgreSQL real

La auditoria de `PATCH /api/v1/users/{user_id}/status` queda validada a nivel de
servicio mediante repositorio y auditor fakes. No se ejecuto una prueba de
integracion contra PostgreSQL real que confirme la fila final en `audit_events`.

**Impacto:** bajo para este avance; la ruta llama al servicio correcto y el
servicio invoca `record_administrative_action` para cambios efectivos de estado.

**Recomendacion:** agregar prueba de integracion con base de datos real o
contenedor PostgreSQL antes del cierre tecnico del MVP.

### QA-MIN-002 - Semantica de auditoria para PATCH idempotente pendiente de definir

`UserService.update_user_status` retorna sin auditar si el estado solicitado es
igual al estado actual. La validacion actual aprueba la auditoria del cambio
efectivo de estado, pero no define si una solicitud administrativa sin cambio
tambien debe registrarse.

**Impacto:** bajo; no bloquea noticias/comunicados, pero conviene definirlo
antes de endurecer auditoria completa.

**Recomendacion:** si la regla "toda accion administrativa" incluye intentos
idempotentes, backend debe auditar tambien ese caso y QA debe agregar la prueba.

---

## Decision de avance

El backend puede avanzar al modulo de noticias/comunicados.

Condiciones para el siguiente modulo:

- Mantener `require_permissions(...)` con permisos explicitos por endpoint.
- No autorizar por claims autocontenidos del JWT.
- Validar sesion vigente, usuario `ACTIVE` y permisos actuales contra base de
  datos.
- Registrar auditoria para acciones administrativas mutantes.
- Agregar pruebas negativas por cada endpoint administrativo nuevo.

---

# Reporte QA - noticias y comunicados

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_news_announcements  
**Alcance:** `app/backend/`, `tests/backend/`, `app/database/schema.sql`,
`app/database/seed.sql`, contrato API y documentos de coordinacion.

---

## Resultado ejecutivo

El modulo backend de noticias y comunicados queda validado para avanzar al
modulo de eventos.

La revision confirma que:

- los endpoints implementados estan bajo `/api/v1` y coinciden con el contrato
  funcional vigente;
- `GET /api/v1/news` y `GET /api/v1/announcements` solo exponen contenido
  `PUBLISHED` por defecto;
- `GET /api/v1/news/{news_id}` no expone noticias `DRAFT` ni `ARCHIVED` a
  usuarios publicos;
- los filtros administrativos de noticias para `DRAFT` o `ARCHIVED` requieren
  permiso vigente `content.publish`;
- `POST`, `PATCH`, `DELETE` y `publish` usan `require_permissions(...)`;
- usuarios sin sesion reciben `401` en acciones administrativas;
- usuarios sin permiso reciben `403`;
- usuarios con permiso pueden crear, actualizar, archivar y publicar noticias;
- usuarios con permiso pueden crear, actualizar y publicar comunicados;
- publicar asigna estado `PUBLISHED` y `published_at`;
- `DELETE /api/v1/news/{news_id}` archiva la noticia y conserva la fila logica;
- las acciones mutantes revisadas registran auditoria administrativa;
- contenido vacio se rechaza al crear y publicar;
- las respuestas revisadas respetan el envelope `{ data, message, errors }`.

---

## Matriz de validacion

| Criterio | Resultado | Evidencia |
| --- | --- | --- |
| Endpoints coinciden con `docs/API_CONTRACT.md` | Aprobado con observacion menor | `app/backend/api/v1/news.py`, `app/backend/api/v1/announcements.py` |
| Listados publicos no exponen `DRAFT` ni `ARCHIVED` | Aprobado | `test_public_user_can_list_published_news`, `test_archived_news_is_not_in_public_listing`, `test_public_user_can_list_only_published_announcements` |
| Detalle publico de noticia no expone borradores/archivados | Aprobado | `test_public_user_does_not_see_drafts`, `test_public_user_does_not_see_archived_news_detail` |
| Mutaciones requieren permiso vigente | Aprobado | `test_mutating_content_routes_require_content_publish_permission` |
| Sin sesion recibe `401` | Aprobado | `test_mutating_content_routes_require_session` |
| Sin permiso recibe `403` | Aprobado | pruebas negativas de noticias y comunicados |
| Usuario con permiso puede crear, actualizar, archivar y publicar noticias | Aprobado | `test_user_with_permission_can_update_archive_and_publish_news_via_routes` |
| Usuario con permiso puede crear, actualizar y publicar comunicados | Aprobado | `test_user_with_permission_can_create_update_and_publish_announcement_via_routes` |
| Publicar asigna `PUBLISHED` y `published_at` | Aprobado | pruebas de publish por ruta y servicio |
| Archivar no borra fisicamente | Aprobado | `test_user_with_permission_can_update_archive_and_publish_news_via_routes` |
| Mutaciones generan auditoria | Aprobado | pruebas con `RecordingAuditor` |
| Contenido vacio no se publica ni crea | Aprobado | `test_empty_content_is_rejected_for_news_and_announcements`, `test_publish_empty_news_and_announcement_content_is_rejected` |
| Comunicados siguen reglas equivalentes | Aprobado | pruebas de listado, permisos, create/update/publish y contenido vacio |
| Formato estandar de respuesta | Aprobado | asserts de `data`, `message`, `errors` |

---

## Pruebas ejecutadas

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado inicial antes de ampliar cobertura: `53 passed, 1 warning`.

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado despues de ampliar cobertura: `62 passed, 1 warning`.

```bash
pytest -q --basetemp .pytest-tmp
```

Resultado global del repositorio: `66 passed, 1 warning`.

---

## Hallazgos criticos

No se detectaron hallazgos criticos en el modulo revisado.

---

## Hallazgos medios

No se detectaron hallazgos medios bloqueantes.

---

## Hallazgos menores

### QA-MIN-003 - Respuesta de archivado de noticia es mas amplia que el ejemplo contractual

`DELETE /api/v1/news/{news_id}` esta documentado con `data` minimo `{ id,
status }`, mientras la implementacion retorna `NewsResponse` completo. No rompe
seguridad ni consumidores que ignoren campos extra, pero conviene alinear
contrato e implementacion antes de integracion frontend estricta.

### QA-MIN-004 - Auditoria persistida no se valida contra PostgreSQL real

La auditoria de noticias y comunicados queda validada a nivel de servicio con
`RecordingAuditor`. No se ejecuto una prueba de integracion contra PostgreSQL
real que confirme las filas finales en `audit_events`.

### QA-MIN-005 - Mutaciones idempotentes no registran auditoria

Archivar una noticia ya `ARCHIVED` o publicar contenido ya `PUBLISHED` retorna
el registro existente sin auditoria nueva. La validacion aprueba auditoria para
mutaciones efectivas; si la regla "toda accion administrativa" incluye intentos
idempotentes, backend debe definir y auditar esos casos.

---

## Decision de avance

El backend puede avanzar al modulo de eventos.

Condiciones para el siguiente modulo:

- Mantener `require_permissions(...)` con permisos explicitos por endpoint.
- Mantener lecturas publicas filtradas por estados publicables.
- Registrar auditoria para acciones administrativas mutantes.
- Agregar pruebas negativas de `401`, `403`, estado no publicable y contenido
  invalido por cada endpoint nuevo.

---

# Reporte QA - eventos, inscripciones y asistencia

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_events  
**Alcance:** `app/backend/`, `tests/backend/`, `app/database/schema.sql`,
`app/database/seed.sql`, contrato API y documentos de coordinacion.

---

## Resultado ejecutivo

El modulo backend de eventos, inscripciones y asistencia queda validado para
avanzar al modulo de solicitudes estudiantiles.

La revision confirma que:

- los endpoints implementados estan bajo `/api/v1` y coinciden con el contrato
  funcional vigente;
- `GET /api/v1/events` solo expone eventos `PUBLISHED` proximos por defecto;
- eventos `PLANNED`, `CANCELLED` y `FINISHED` no se exponen en lecturas publicas
  sin permiso;
- filtros administrativos de estados no publicos requieren `events.manage`;
- `POST`, `PATCH`, `publish`, `cancel`, `finish` y `attendance` usan
  `require_permissions(...)` con `events.manage`;
- inscripcion y cancelacion de inscripcion requieren usuario autenticado;
- usuarios sin sesion reciben `401` en acciones protegidas;
- usuarios sin permiso reciben `403` en acciones administrativas;
- usuarios con `events.manage` pueden crear, actualizar, publicar, cancelar,
  finalizar eventos y registrar asistencia;
- crear, actualizar, publicar, cancelar, finalizar y registrar asistencia
  generan auditoria administrativa a nivel de servicio;
- el motivo de cancelacion queda en metadata de auditoria;
- fechas invalidas (`ends_at <= starts_at`) se rechazan al crear y actualizar;
- la capacidad se respeta al registrar usuarios;
- no se permite inscripcion duplicada;
- no se permite inscripcion a eventos no publicados;
- un usuario puede cancelar su propia inscripcion sin afectar otras;
- asistencia requiere inscripcion previa;
- las respuestas revisadas respetan el envelope `{ data, message, errors }`.

---

## Matriz de validacion

| Criterio | Resultado | Evidencia |
| --- | --- | --- |
| Endpoints coinciden con `docs/API_CONTRACT.md` | Aprobado | `app/backend/api/v1/events.py`, `tests/backend/test_events_module.py` |
| Listado publico no expone `PLANNED`, `CANCELLED`, `FINISHED` ni eventos pasados | Aprobado | `test_public_user_only_sees_published_upcoming_events` |
| Detalle publico no expone estados no publicos | Aprobado | `test_public_user_does_not_see_planned_events`, `test_public_user_does_not_see_non_public_event_details` |
| Estados no publicos por filtro requieren `events.manage` | Aprobado | `test_admin_can_filter_non_public_events_with_permission`, `test_authenticated_user_without_permission_cannot_filter_non_public_events` |
| Acciones administrativas requieren sesion | Aprobado | `test_admin_event_routes_require_session` |
| Acciones administrativas requieren `events.manage` | Aprobado | `test_admin_event_routes_require_events_manage_permission` |
| Usuario con permiso puede crear, actualizar, publicar, cancelar, finalizar y registrar asistencia | Aprobado | `test_user_with_permission_can_update_publish_cancel_finish_and_attend_via_routes` |
| Auditoria administrativa para mutaciones | Aprobado | pruebas con `RecordingAuditor` |
| Fecha fin anterior o igual a inicio se rechaza | Aprobado | `test_end_date_before_start_returns_error`, `test_update_event_rejects_end_before_existing_start` |
| Capacidad se respeta | Aprobado | `test_user_cannot_register_when_capacity_is_full` |
| No hay inscripcion duplicada | Aprobado | `test_user_cannot_register_twice` |
| No hay inscripcion en evento no publicado | Aprobado | `test_user_cannot_register_to_unpublished_event` |
| Usuario autenticado puede inscribirse sin permiso administrativo | Aprobado | `test_authenticated_user_without_event_permissions_can_register` |
| Cancelacion de inscripcion propia no afecta a otros | Aprobado | `test_cancel_registration_does_not_affect_other_users` |
| Asistencia requiere inscripcion previa | Aprobado | `test_attendance_requires_previous_registration` |
| Formato estandar de respuesta | Aprobado | asserts de `data`, `message`, `errors` |

---

## Pruebas ejecutadas

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado inicial antes de ampliar cobertura: `79 passed, 1 warning`.

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado despues de ampliar cobertura: `93 passed, 1 warning`.

```bash
pytest -q --basetemp .pytest-tmp
```

Resultado global del repositorio: `97 passed, 1 warning`.

---

## Hallazgos criticos

No se detectaron hallazgos criticos en el modulo revisado.

---

## Hallazgos medios

No se detectaron hallazgos medios bloqueantes.

---

## Hallazgos menores

### QA-MIN-006 - Auditoria persistida no se valida contra PostgreSQL real

La auditoria de eventos queda validada a nivel de servicio con
`RecordingAuditor`. No se ejecuto una prueba de integracion contra PostgreSQL
real que confirme las filas finales en `audit_events`.

### QA-MIN-007 - Mutaciones idempotentes no registran auditoria nueva

Publicar un evento ya `PUBLISHED`, cancelar un evento ya `CANCELLED`, finalizar
un evento ya `FINISHED` o registrar asistencia ya existente retorna el registro
existente sin crear un nuevo evento de auditoria. La validacion aprueba auditoria
para mutaciones efectivas; si la regla "toda accion administrativa" incluye
intentos idempotentes, backend debe definir y auditar esos casos.

---

## Decision de avance

El backend puede avanzar al modulo de solicitudes estudiantiles.

Condiciones para el siguiente modulo:

- Mantener `require_permissions(...)` con permisos explicitos en acciones
  administrativas.
- Mantener lecturas publicas filtradas por estados publicables.
- Registrar auditoria para acciones administrativas mutantes.
- Agregar pruebas negativas de `401`, `403`, transiciones invalidas y reglas de
  negocio por cada endpoint nuevo.

---

# Reporte QA - solicitudes estudiantiles

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_requests  
**Alcance:** `app/backend/`, `tests/backend/`, `app/database/schema.sql`,
`app/database/seed.sql`, contrato API y documentos de coordinacion.

---

## Resultado ejecutivo

El modulo backend de solicitudes estudiantiles queda validado para avanzar al
modulo de documentos/archivos.

La revision confirma que:

- los endpoints implementados estan bajo `/api/v1` y coinciden con el contrato
  funcional vigente;
- `POST /api/v1/requests` requiere sesion valida y permiso vigente
  `requests.create`;
- las solicitudes nuevas quedan en `SUBMITTED` y generan historial inicial en
  `request_status_history`;
- estudiantes solo listan, consultan, editan y comentan solicitudes propias;
- usuarios con `requests.manage` pueden listar todas, usar filtros
  administrativos, actualizar campos administrativos y gestionar estados;
- `scope=all`, filtros por `status` y filtros por `category_id` devuelven `403`
  sin `requests.manage`;
- acciones administrativas `assign`, `observe`, `approve`, `reject` y `close`
  devuelven `401` sin sesion y `403` sin `requests.manage`;
- estudiantes pueden editar solicitudes propias en `SUBMITTED` u `OBSERVED`;
- estudiantes no pueden editar solicitudes `CLOSED`, `APPROVED` o `REJECTED`;
- estudiantes no pueden modificar campos administrativos;
- asignar responsable cambia a `IN_REVIEW` cuando corresponde, registra
  historial y auditoria;
- observar y rechazar exigen motivo no vacio;
- observar, aprobar, rechazar y cerrar generan historial y auditoria
  administrativa cuando cambian estado;
- no se puede aprobar una solicitud `CLOSED` o `REJECTED`;
- el cierre es administrativo segun `DEC-013`;
- comentarios solo pueden ser creados por el solicitante o por usuarios con
  `requests.manage`;
- comentarios internos requieren `requests.manage` y no se exponen al
  solicitante;
- las respuestas revisadas respetan el envelope `{ data, message, errors }`.

---

## Matriz de validacion

| Criterio | Resultado | Evidencia |
| --- | --- | --- |
| Endpoints coinciden con `docs/API_CONTRACT.md` | Aprobado | `app/backend/api/v1/requests.py`, `tests/backend/test_requests_module.py` |
| Estudiante puede crear solicitud con `requests.create` | Aprobado | `test_authenticated_user_can_create_request` |
| Solicitud creada queda en `SUBMITTED` | Aprobado | `test_authenticated_user_can_create_request`, `test_created_request_has_initial_status_history` |
| Creacion genera historial inicial | Aprobado | `test_created_request_has_initial_status_history` |
| Estudiante lista solo solicitudes propias | Aprobado | `test_student_lists_only_own_requests` |
| Estudiante no ve solicitud ajena | Aprobado | `test_student_cannot_see_other_student_request` |
| Usuario sin sesion no puede crear | Aprobado | `test_user_without_session_cannot_create_request` |
| Usuario sin `requests.create` no puede crear | Aprobado | `test_user_without_requests_create_permission_cannot_create_request` |
| Usuario sin `requests.manage` no puede listar todas ni filtrar administrativamente | Aprobado | `test_user_without_permission_cannot_list_all_requests`, `test_user_without_permission_cannot_use_administrative_filters` |
| Usuario con `requests.manage` puede listar todas y filtrar | Aprobado | `test_user_with_manage_permission_can_list_all_requests`, `test_user_with_manage_permission_can_filter_all_requests` |
| Estudiante puede editar solicitud propia `SUBMITTED` u `OBSERVED` | Aprobado | `test_student_can_edit_own_submitted_request`, `test_student_can_edit_own_observed_request` |
| Estudiante no edita `CLOSED`, `APPROVED` o `REJECTED` | Aprobado | `test_student_cannot_edit_closed_request`, `test_student_cannot_edit_terminal_request_states` |
| Estudiante no modifica campos administrativos | Aprobado | `test_student_cannot_update_administrative_fields` |
| PATCH administrativo actualiza campos administrativos y audita | Aprobado | `test_administrative_patch_updates_admin_fields_and_audits` |
| Acciones administrativas requieren sesion y `requests.manage` | Aprobado | `test_administrative_request_routes_require_session`, `test_administrative_request_routes_require_manage_permission` |
| Asignar responsable genera auditoria e historial si cambia estado | Aprobado | `test_administrative_user_can_assign_responsible_and_audit` |
| Observar requiere motivo, cambia a `OBSERVED` y genera historial | Aprobado | `test_reason_required_for_observe_and_reject_routes`, `test_administrative_user_can_observe_with_reason_and_history` |
| Aprobar cambia a `APPROVED`, genera historial y auditoria | Aprobado | `test_administrative_user_can_approve_with_history_and_audit` |
| Rechazar requiere motivo, genera historial y auditoria | Aprobado | `test_reason_required_for_observe_and_reject_routes`, `test_administrative_user_can_reject_with_reason_history_and_audit` |
| No se aprueba solicitud `CLOSED` o `REJECTED` | Aprobado | `test_cannot_approve_closed_request`, `test_cannot_approve_rejected_request` |
| Cerrar cambia a `CLOSED` bajo regla administrativa | Aprobado | `test_administrative_user_can_close_with_history_and_audit` |
| Categoria invalida se rechaza | Aprobado | `test_invalid_request_category_is_rejected` |
| Comentarios limitados a propietario o administrador | Aprobado | `test_comments_are_limited_to_owner_or_admin`, `test_owner_can_create_comment_via_route`, `test_non_owner_cannot_create_comment_via_route` |
| Comentarios internos requieren `requests.manage` | Aprobado | `test_owner_cannot_create_internal_comment`, `test_admin_can_view_internal_comments` |
| Formato estandar de respuesta | Aprobado | asserts de `data`, `message`, `errors` en rutas revisadas |

---

## Pruebas ejecutadas

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado inicial antes de ampliar cobertura: `110 passed, 1 warning`.

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado despues de ampliar cobertura: `129 passed, 1 warning`.

```bash
pytest -q --basetemp .pytest-tmp
```

Resultado global del repositorio: `133 passed, 1 warning`.

---

## Hallazgos criticos

No se detectaron hallazgos criticos en el modulo revisado.

---

## Hallazgos medios

No se detectaron hallazgos medios bloqueantes.

---

## Hallazgos menores

### QA-MIN-008 - Auditoria persistida no se valida contra PostgreSQL real

La auditoria de solicitudes queda validada a nivel de servicio con
`RecordingAuditor`. No se ejecuto una prueba de integracion contra PostgreSQL
real que confirme las filas finales en `audit_events`.

### QA-MIN-009 - Semantica idempotente de acciones administrativas pendiente

El modulo audita las acciones administrativas mutantes revisadas. Cuando una
accion no produce una transicion nueva de estado, no se crea historial adicional
porque no existe cambio de estado. Si el producto decide que intentos
idempotentes deben rechazarse o historizarse, backend debe formalizarlo en una
decision y QA debe agregar pruebas especificas.

---

## Decision de avance

El backend puede avanzar al modulo de documentos/archivos.

Finanzas basicas queda tambien desbloqueada a nivel de seguridad y QA, pero el
siguiente modulo recomendado es documentos/archivos porque las solicitudes ya
dejaron pendiente `POST /requests/{id}/attachments` y `SECURITY_REVIEW.md`
exige controles de tipo, tamano, nombre seguro, almacenamiento privado y
descarga autorizada antes de implementar archivos.

---

# Reporte QA - documentos, archivos y adjuntos

**Fecha:** 2026-06-24
**Agente:** agent.qa_engineer
**Fase:** qa_documents_files
**Alcance:** `app/backend/`, `app/backend/documents/`, `app/backend/files/`,
`tests/backend/test_documents_module.py`, modelo de datos, contrato API,
revision de seguridad y documentos de coordinacion.

---

## Resultado ejecutivo

El modulo backend de documentos, archivos y adjuntos de solicitudes queda
validado funcionalmente y puede dar paso al modulo de finanzas basicas.

La revision confirma que:

- los nueve endpoints implementados coinciden con el contrato vigente;
- el listado y detalle publicos exponen solo documentos `PUBLISHED` y `PUBLIC`;
- documentos privados, borradores y filtros administrativos requieren
  `documents.manage`;
- `POST`, `PATCH` y `DELETE /documents` devuelven `401` sin sesion y `403` sin
  `documents.manage`;
- las subidas aceptan PDF, PNG, JPEG, DOCX, XLSX y CSV validos;
- archivos vacios, sobredimensionados, con extension/MIME no permitidos o firma
  inconsistente son rechazados;
- cada archivo recibe nombre interno UUID, nombre publico sanitizado y SHA-256;
- las respuestas no exponen `storage_key`, `file_url` ni rutas fisicas;
- `PATCH` actualiza metadatos, asigna `published_at` al publicar y audita;
- `DELETE` realiza archivado logico, conserva el archivo y audita;
- el solicitante puede crear, listar y descargar adjuntos de su solicitud;
- usuarios ajenos reciben `404` al intentar listar, adjuntar o descargar;
- `requests.manage` permite revision y carga administrativa de adjuntos;
- solicitudes `CLOSED`, `APPROVED` o `REJECTED` no aceptan adjuntos;
- los errores JSON revisados mantienen `{ data, message, errors }` y las
  descargas exitosas son binarias con `Content-Disposition` seguro.

---

## Matriz de validacion

| Criterio | Resultado | Evidencia |
| --- | --- | --- |
| Endpoints coinciden con `docs/API_CONTRACT.md` | Aprobado | `app/backend/api/v1/documents.py`, rutas de adjuntos en `app/backend/api/v1/requests.py` |
| Listado publico muestra solo documentos publicos | Aprobado | `test_public_user_lists_only_public_documents` |
| Documento privado no es visible ni descargable sin permiso | Aprobado | `test_public_user_cannot_download_private_document`, `test_authenticated_user_without_permission_cannot_view_or_download_private_document` |
| `documents.manage` permite ver y descargar documentos privados | Aprobado | `test_user_with_documents_manage_can_view_and_download_private_document` |
| Filtros administrativos requieren `documents.manage` | Aprobado | `test_document_filters_require_documents_manage` |
| Subida administrativa requiere sesion y permiso | Aprobado | `test_administrative_document_routes_require_session`, `test_user_without_documents_permission_cannot_upload_document` |
| PDF, PNG, JPEG, DOCX, XLSX y CSV validos son aceptados | Aprobado | `test_all_allowed_file_types_are_accepted` |
| SHA-256 calculado | Aprobado | `test_uploaded_document_calculates_sha256`, `test_all_allowed_file_types_are_accepted` |
| Nombre interno UUID y sin sobrescritura | Aprobado | `test_uploaded_document_uses_unique_uuid_storage_names` |
| Respuesta no expone rutas internas | Aprobado | `test_user_with_documents_manage_can_upload_document`, `test_download_does_not_expose_internal_path` |
| Archivo vacio rechazado | Aprobado | `test_empty_file_is_rejected` |
| Archivo mayor al limite rechazado | Aprobado | `test_file_larger_than_maximum_is_rejected`, `test_multipart_stream_without_content_length_is_limited` |
| Tipo no permitido rechazado | Aprobado | `test_file_with_disallowed_type_is_rejected` |
| Ejecutable renombrado rechazado | Aprobado | `test_renamed_executable_with_pdf_mime_is_rejected` |
| Nombre malicioso no altera almacenamiento | Aprobado | `test_malicious_filename_does_not_affect_storage_path` |
| `PATCH` actualiza, publica y audita | Aprobado | `test_patch_updates_metadata_and_records_audit`, `test_patch_to_published_assigns_published_at` |
| Categoria invalida rechazada | Aprobado | `test_invalid_document_category_is_rejected` |
| `PATCH` y `DELETE` requieren `documents.manage` | Aprobado | `test_patch_and_delete_require_documents_manage` |
| `DELETE` es logico y oculta el documento publico | Aprobado | `test_delete_performs_logical_deletion` |
| Dueno puede adjuntar, listar y descargar | Aprobado | `test_request_owner_can_attach_file`, `test_request_owner_can_list_and_download_attachments` |
| Usuario ajeno no puede adjuntar, listar ni descargar | Aprobado | `test_non_owner_cannot_attach_to_other_request`, `test_other_user_cannot_list_request_attachments`, `test_other_user_cannot_download_request_attachment` |
| `requests.manage` permite adjuntar, listar y descargar | Aprobado | `test_user_with_requests_manage_can_attach_administratively`, `test_requests_manage_can_list_and_download_request_attachments` |
| Estados terminales no aceptan adjuntos | Aprobado | `test_cannot_attach_to_terminal_request` |
| Adjuntos requieren sesion | Aprobado | `test_request_attachment_upload_requires_session`, `test_request_attachment_reads_require_session` |
| Adjuntos administrativos generan auditoria | Aprobado | `test_user_with_requests_manage_can_attach_administratively` |
| Envelope estandar en respuestas JSON | Aprobado | asserts de `assert_standard_response_shape` en rutas positivas y negativas |

---

## Pruebas ejecutadas

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado inicial: `150 passed, 1 warning`.

Se agregaron 24 pruebas funcionales y de autorizacion.

```bash
pytest -q tests/backend --basetemp .pytest-tmp
```

Resultado final backend: `174 passed, 1 warning`.

```bash
pytest -q --basetemp .pytest-tmp
```

Resultado global: `178 passed, 1 warning`.

El warning corresponde a la deprecacion de `TestClient` de Starlette con
`httpx`; no afecta el resultado funcional.

---

## Hallazgos criticos

No se detectaron hallazgos criticos abiertos.

---

## Hallazgos medios

No se detectaron defectos funcionales medios bloqueantes durante QA.

Se mantienen como riesgos medios de produccion los hallazgos ya registrados por
seguridad:

- parser multipart local con menor madurez que una libreria mantenida;
- ausencia de cuarentena y escaneo antimalware;
- riesgo de CSV injection;
- falta de validacion estricta del aislamiento y limites del almacenamiento en
  produccion;
- SHA-256 sidecar no verificado al descargar y limpieza no garantizada de
  archivos huerfanos.

Estos riesgos no bloquean el avance funcional a finanzas, pero si bloquean
habilitar cargas no confiables en produccion.

---

## Hallazgos menores

### QA-MIN-010 - Persistencia real no validada contra PostgreSQL

La auditoria, el archivado y los metadatos se validaron mediante repositorios y
auditores de prueba. No se ejecuto una integracion con PostgreSQL real y
almacenamiento persistente que confirme en conjunto `audit_events`,
`deleted_at`, `document_versions` y `request_attachments`.

### QA-MIN-011 - Advertencia de deprecacion en la infraestructura de tests

Las suites emiten `StarletteDeprecationWarning` por el uso de `httpx` desde
`starlette.testclient`. No afecta los resultados actuales, pero conviene
actualizar la dependencia o el cliente de pruebas antes de que la compatibilidad
se rompa.

---

## Decision de avance

El backend puede avanzar a finanzas basicas.

No es necesario devolver el modulo a backend por un defecto funcional de QA.
Sin embargo, `Handoff 027` permanece pendiente y el hardening de antimalware,
CSV injection y aislamiento del almacenamiento debe completarse antes de
habilitar cargas de archivos no confiables en produccion.
