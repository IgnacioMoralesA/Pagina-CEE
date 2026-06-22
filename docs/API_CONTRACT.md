# API_CONTRACT.md

# Contrato API inicial — CEE Conecta

## 1. Propósito

Este documento define el contrato inicial de la API REST.

El backend debe respetar este contrato y el frontend no debe inventar endpoints fuera de este documento.

---

## 2. Convenciones

Base path:

```text
/api/v1
```

Formato de respuesta estándar:

```json
{
  "data": {},
  "message": "string",
  "errors": []
}
```

Formato de error estándar:

```json
{
  "data": null,
  "message": "Descripción del error",
  "errors": [
    {
      "field": "campo",
      "detail": "detalle"
    }
  ]
}
```

## 2.1 Health checks

## GET /health

Retorna el estado basico del servicio.

### Salida

```json
{
  "data": {
    "status": "ok",
    "service": "CEE Conecta API",
    "version": "0.1.0",
    "environment": "local"
  },
  "message": "Servicio disponible",
  "errors": []
}
```

## GET /health/database

Verifica la conexion configurada hacia PostgreSQL.

Requiere usuario autenticado con permiso vigente `system.admin`.

Si PostgreSQL no esta disponible, el endpoint responde con `200` y
`data.status = "unavailable"` sin exponer clases internas ni detalles tecnicos.

### Salida

```json
{
  "data": {
    "status": "ok",
    "detail": null
  },
  "message": "Base de datos disponible",
  "errors": []
}
```

---

## 3. Autenticación

## POST /auth/google

Valida un token de Google y crea una sesión local.

### Entrada

```json
{
  "id_token": "string"
}
```

### Salida

```json
{
  "data": {
    "access_token": "string",
    "token_type": "bearer",
    "expires_at": "datetime",
    "user": {
      "id": "uuid",
      "email": "string",
      "name": "string",
      "role": "STUDENT",
      "roles": ["STUDENT"],
      "permissions": ["events.register", "requests.create"]
    }
  },
  "message": "Login correcto",
  "errors": []
}
```

---

## GET /users/me

Retorna el usuario autenticado.

### Headers

```text
Authorization: Bearer <access_token>
```

### Salida

```json
{
  "data": {
    "id": "uuid",
    "email": "string",
    "name": "string",
    "role": "STUDENT",
    "roles": ["STUDENT"],
    "permissions": ["events.register", "requests.create"]
  },
  "message": "Usuario autenticado",
  "errors": []
}
```

---

## 3.1 Usuarios, roles y permisos administrativos

Todos los endpoints de esta seccion requieren:

```text
Authorization: Bearer <access_token>
```

La autorizacion se evalua con sesion activa, usuario `ACTIVE` y permisos
vigentes desde base de datos. No se deben usar roles o permisos autocontenidos
en el JWT como fuente final de autorizacion.

## GET /users

Lista usuarios no eliminados.

Permiso requerido: `users.manage`.

### Salida

```json
{
  "data": [
    {
      "id": "uuid",
      "email": "string",
      "name": "string",
      "avatar_url": null,
      "status": "ACTIVE",
      "last_login_at": "datetime",
      "created_at": "datetime",
      "updated_at": "datetime",
      "roles": ["ADMIN"],
      "permissions": ["users.manage"]
    }
  ],
  "message": "Usuarios obtenidos",
  "errors": []
}
```

## GET /users/{user_id}

Retorna un usuario no eliminado.

Permiso requerido: `users.manage`.

### Salida

```json
{
  "data": {
    "id": "uuid",
    "email": "string",
    "name": "string",
    "avatar_url": null,
    "status": "ACTIVE",
    "last_login_at": "datetime",
    "created_at": "datetime",
    "updated_at": "datetime",
    "roles": ["ADMIN"],
    "permissions": ["users.manage"]
  },
  "message": "Usuario obtenido",
  "errors": []
}
```

## PATCH /users/{user_id}/status

Actualiza el estado de un usuario no eliminado y registra auditoria
administrativa.

Permiso requerido: `users.manage`.

### Entrada

```json
{
  "status": "ACTIVE"
}
```

Valores permitidos: `ACTIVE`, `INACTIVE`, `SUSPENDED`.

### Salida

```json
{
  "data": {
    "id": "uuid",
    "email": "string",
    "name": "string",
    "avatar_url": null,
    "status": "SUSPENDED",
    "last_login_at": "datetime",
    "created_at": "datetime",
    "updated_at": "datetime",
    "roles": ["ADMIN"],
    "permissions": ["users.manage"]
  },
  "message": "Estado de usuario actualizado",
  "errors": []
}
```

## GET /roles

Lista roles del sistema con sus permisos asignados.

Permiso requerido: `roles.manage`.

### Salida

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "ADMIN",
      "display_name": "Administrador",
      "description": "string",
      "is_system": true,
      "permissions": ["users.manage", "roles.manage"]
    }
  ],
  "message": "Roles obtenidos",
  "errors": []
}
```

## GET /permissions

Lista permisos disponibles.

Permiso requerido: `roles.manage`.

### Salida

```json
{
  "data": [
    {
      "id": "uuid",
      "code": "users.manage",
      "module": "users",
      "action": "manage",
      "description": "string",
      "is_system": true
    }
  ],
  "message": "Permisos obtenidos",
  "errors": []
}
```

---

## 4. Noticias

## GET /news

Lista noticias publicadas. Es publico por defecto y soporta paginacion basica.

### Query params

- `limit`: entero entre `1` y `100`. Valor por defecto: `20`.
- `offset`: entero mayor o igual a `0`. Valor por defecto: `0`.
- `category_id`: UUID opcional.
- `status`: `PUBLISHED`, `DRAFT` o `ARCHIVED`. Solo `PUBLISHED` es publico;
  consultar `DRAFT` o `ARCHIVED` requiere permiso vigente `content.publish`.

### Salida

```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "string",
        "slug": "string",
        "summary": "string",
        "content": "string",
        "author_id": "uuid",
        "author_name": "string",
        "category_id": "uuid",
        "category_name": "string",
        "category_slug": "string",
        "status": "PUBLISHED",
        "published_at": "datetime",
        "image_url": null,
        "created_at": "datetime",
        "updated_at": "datetime"
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
  },
  "message": "Noticias obtenidas",
  "errors": []
}
```

## GET /news/{news_id}

Retorna una noticia publicada para usuarios publicos. Si la noticia esta en
`DRAFT` o `ARCHIVED`, requiere bearer token con permiso vigente
`content.publish`; sin ese permiso no se exponen borradores.

## POST /news

Crea una noticia en estado `DRAFT` y registra auditoria administrativa.

Permiso requerido: `content.publish`.

### Entrada

```json
{
  "title": "string",
  "summary": "string",
  "content": "string",
  "category_id": "uuid",
  "image_url": "string"
}
```

### Salida

```json
{
  "data": {
    "id": "uuid",
    "title": "string",
    "slug": "string",
    "summary": "string",
    "content": "string",
    "author_id": "uuid",
    "author_name": "string",
    "category_id": "uuid",
    "category_name": "string",
    "category_slug": "string",
    "status": "DRAFT",
    "published_at": null,
    "image_url": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "message": "Noticia creada",
  "errors": []
}
```

## PATCH /news/{news_id}

Actualiza una noticia no archivada y registra auditoria administrativa.

Permiso requerido: `content.publish`.

No permite editar noticias `ARCHIVED`.

### Entrada

```json
{
  "title": "string",
  "summary": "string",
  "content": "string",
  "category_id": "uuid",
  "image_url": "string"
}
```

## DELETE /news/{news_id}

Archiva una noticia cambiando su estado a `ARCHIVED`; no realiza borrado fisico.
Registra auditoria administrativa.

Permiso requerido: `content.publish`.

### Salida

```json
{
  "data": {
    "id": "uuid",
    "status": "ARCHIVED"
  },
  "message": "Noticia archivada",
  "errors": []
}
```

## POST /news/{news_id}/publish

Publica una noticia no archivada, cambia su estado a `PUBLISHED`, asigna
`published_at` y registra auditoria administrativa.

Permiso requerido: `content.publish`.

---

## 5. Comunicados

## GET /announcements

Lista comunicados publicados. Es publico y soporta paginacion basica.

### Query params

- `limit`: entero entre `1` y `100`. Valor por defecto: `20`.
- `offset`: entero mayor o igual a `0`. Valor por defecto: `0`.

### Salida

```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "title": "string",
        "slug": "string",
        "summary": "string",
        "content": "string",
        "author_id": "uuid",
        "author_name": "string",
        "category_id": "uuid",
        "category_name": "string",
        "category_slug": "string",
        "status": "PUBLISHED",
        "priority": 3,
        "published_at": "datetime",
        "expires_at": null,
        "created_at": "datetime",
        "updated_at": "datetime"
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
  },
  "message": "Comunicados obtenidos",
  "errors": []
}
```

## POST /announcements

Crea un comunicado en estado `DRAFT` y registra auditoria administrativa.

Permiso requerido: `content.publish`.

### Entrada

```json
{
  "title": "string",
  "summary": "string",
  "content": "string",
  "category_id": "uuid",
  "priority": 3,
  "expires_at": "datetime"
}
```

## PATCH /announcements/{announcement_id}

Actualiza un comunicado no archivado y registra auditoria administrativa.

Permiso requerido: `content.publish`.

### Entrada

```json
{
  "title": "string",
  "summary": "string",
  "content": "string",
  "category_id": "uuid",
  "priority": 3,
  "expires_at": "datetime"
}
```

## POST /announcements/{announcement_id}/publish

Publica un comunicado no archivado, cambia su estado a `PUBLISHED`, asigna
`published_at` y registra auditoria administrativa.

Permiso requerido: `content.publish`.

---

## 6. Eventos

- `GET /events`
- `POST /events`
- `GET /events/{event_id}`
- `PATCH /events/{event_id}`
- `POST /events/{event_id}/publish`
- `POST /events/{event_id}/register`
- `DELETE /events/{event_id}/registration`
- `POST /events/{event_id}/attendance`

---

## 7. Solicitudes estudiantiles

- `GET /requests`
- `POST /requests`
- `GET /requests/{request_id}`
- `PATCH /requests/{request_id}`
- `POST /requests/{request_id}/attachments`
- `POST /requests/{request_id}/assign`
- `POST /requests/{request_id}/approve`
- `POST /requests/{request_id}/reject`
- `POST /requests/{request_id}/close`

---

## 8. Documentos

- `GET /documents`
- `POST /documents`
- `GET /documents/{document_id}`
- `GET /documents/{document_id}/download`
- `PATCH /documents/{document_id}`
- `DELETE /documents/{document_id}`

---

## 9. Finanzas

- `GET /budgets`
- `POST /budgets`
- `GET /income-records`
- `POST /income-records`
- `GET /expense-records`
- `POST /expense-records`
- `POST /expense-records/{expense_id}/approve`
- `GET /financial-summary`

---

## 10. Inventario

- `GET /inventory-items`
- `POST /inventory-items`
- `PATCH /inventory-items/{item_id}`
- `POST /resource-loans`
- `POST /resource-loans/{loan_id}/return`

---

## 11. Reuniones y actas

- `GET /meetings`
- `POST /meetings`
- `GET /meetings/{meeting_id}`
- `POST /meetings/{meeting_id}/minutes`
- `POST /meetings/{meeting_id}/agreements`
- `PATCH /agreements/{agreement_id}`

---

## 12. Encuestas

- `GET /surveys`
- `POST /surveys`
- `GET /surveys/{survey_id}`
- `POST /surveys/{survey_id}/responses`

---

## 13. Votaciones

- `GET /votings`
- `POST /votings`
- `POST /votings/{voting_id}/open`
- `POST /votings/{voting_id}/vote`
- `POST /votings/{voting_id}/close`
- `GET /votings/{voting_id}/results`

---

## 14. Auditoría

- `GET /audit-events`

---

## 15. Dashboard

- `GET /dashboard`

Debe incluir:

- últimas noticias;
- próximos eventos;
- solicitudes pendientes;
- estadísticas básicas;
- alertas.

---

## 16. Endpoints pendientes de confirmar

- integración real con Google;
- subida física de archivos;
- reportes exportables;
- notificaciones;
- administración detallada de permisos.

---

## 17. Implementacion base disponible

**Fecha:** 2026-06-21  
**Agente:** agent.backend_developer

Endpoints implementados en la base FastAPI:

- `GET /api/v1/health`
- `GET /api/v1/health/database`
- `POST /api/v1/auth/google`
- `GET /api/v1/users/me`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}/status`
- `GET /api/v1/roles`
- `GET /api/v1/permissions`
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

La validacion real de Google requiere configurar `CEE_GOOGLE_CLIENT_ID`.
El dominio institucional puede restringirse con
`CEE_INSTITUTIONAL_EMAIL_DOMAIN`.
