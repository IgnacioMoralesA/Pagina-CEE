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
