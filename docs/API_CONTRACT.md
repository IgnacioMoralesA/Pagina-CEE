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

## GET /events

Lista eventos publicados y proximos por defecto. Es publico y soporta
paginacion basica.

### Query params

- `limit`: entero entre `1` y `100`. Valor por defecto: `20`.
- `offset`: entero mayor o igual a `0`. Valor por defecto: `0`.
- `category_id`: UUID opcional.
- `status`: `PLANNED`, `PUBLISHED`, `FINISHED` o `CANCELLED`. Solo
  `PUBLISHED` es publico; consultar otros estados requiere permiso vigente
  `events.manage`.

### Salida

```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "category_id": "uuid",
        "category_name": "string",
        "category_slug": "string",
        "name": "string",
        "description": "string",
        "starts_at": "datetime",
        "ends_at": "datetime",
        "location": "string",
        "capacity": 100,
        "registered_count": 10,
        "responsible_id": "uuid",
        "responsible_name": "string",
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
  "message": "Eventos obtenidos",
  "errors": []
}
```

## GET /events/{event_id}

Retorna un evento publicado para usuarios publicos. Si el evento esta en
`PLANNED`, `CANCELLED` o `FINISHED`, requiere bearer token con permiso vigente
`events.manage`.

## POST /events

Crea un evento en estado `PLANNED` y registra auditoria administrativa.

Permiso requerido: `events.manage`.

### Entrada

```json
{
  "name": "string",
  "description": "string",
  "starts_at": "datetime",
  "ends_at": "datetime",
  "location": "string",
  "capacity": 100,
  "category_id": "uuid",
  "image_url": "string"
}
```

## PATCH /events/{event_id}

Actualiza un evento y registra auditoria administrativa.

Permiso requerido: `events.manage`.

Debe mantener `ends_at > starts_at` y `capacity > 0` cuando se informe capacidad.

## POST /events/{event_id}/publish

Publica un evento, cambia su estado a `PUBLISHED`, asigna `published_at` y
registra auditoria administrativa.

Permiso requerido: `events.manage`.

## POST /events/{event_id}/cancel

Cancela un evento, cambia su estado a `CANCELLED` y registra auditoria
administrativa. Si se envia `reason`, se conserva en metadata de auditoria.

Permiso requerido: `events.manage`.

### Entrada opcional

```json
{
  "reason": "string"
}
```

## POST /events/{event_id}/finish

Finaliza un evento, cambia su estado a `FINISHED` y registra auditoria
administrativa.

Permiso requerido: `events.manage`.

## POST /events/{event_id}/register

Registra al usuario autenticado en un evento publicado. No permite duplicados ni
superar capacidad.

Requiere bearer token valido.

### Salida

```json
{
  "data": {
    "id": "uuid",
    "event_id": "uuid",
    "user_id": "uuid",
    "status": "REGISTERED",
    "registered_at": "datetime",
    "cancelled_at": null,
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "message": "Inscripcion registrada",
  "errors": []
}
```

## DELETE /events/{event_id}/registration

Cancela logicamente la inscripcion del usuario autenticado. No afecta
inscripciones de otros usuarios.

Requiere bearer token valido.

## POST /events/{event_id}/attendance

Registra asistencia de un usuario inscrito y registra auditoria administrativa.

Permiso requerido: `events.manage`.

### Entrada

```json
{
  "user_id": "uuid",
  "notes": "string"
}
```

---

## 7. Solicitudes estudiantiles

## GET /requests

Lista solicitudes del usuario autenticado. Si el usuario tiene permiso vigente
`requests.manage`, puede consultar todas usando `scope=all` y filtros
administrativos.

Requiere bearer token valido.

### Query params

- `scope`: `mine` o `all`. `all` requiere `requests.manage`.
- `status`: `SUBMITTED`, `IN_REVIEW`, `OBSERVED`, `APPROVED`, `REJECTED`,
  `CLOSED`. Requiere `requests.manage`.
- `category_id`: UUID opcional. Requiere `requests.manage`.
- `limit`: entero entre `1` y `100`. Valor por defecto: `20`.
- `offset`: entero mayor o igual a `0`. Valor por defecto: `0`.

### Salida

```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "requester_id": "uuid",
        "requester_name": "string",
        "category_id": "uuid",
        "category_name": "string",
        "category_slug": "string",
        "title": "string",
        "description": "string",
        "status": "SUBMITTED",
        "priority": "MEDIUM",
        "assigned_to": null,
        "assigned_to_name": null,
        "resolution": null,
        "resolved_at": null,
        "closed_at": null,
        "created_at": "datetime",
        "updated_at": "datetime",
        "status_history": [],
        "comments": []
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
  },
  "message": "Solicitudes obtenidas",
  "errors": []
}
```

## POST /requests

Crea una solicitud estudiantil en estado `SUBMITTED`. El solicitante siempre es
el usuario autenticado. Registra historial inicial de estado.

Permiso requerido: `requests.create`.

### Entrada

```json
{
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "priority": "MEDIUM"
}
```

## GET /requests/{request_id}

Retorna una solicitud si el usuario autenticado es el solicitante o tiene
permiso vigente `requests.manage`.

## PATCH /requests/{request_id}

Actualiza una solicitud.

- El solicitante puede editar su solicitud solo en `SUBMITTED` u `OBSERVED`.
- El solicitante no puede editar campos administrativos.
- Usuarios con `requests.manage` pueden editar campos administrativos y generan
  auditoria administrativa.
- No se permite editar solicitudes cerradas como accion administrativa general.

### Entrada

```json
{
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "priority": "MEDIUM",
  "assigned_to": "uuid",
  "resolution": "string"
}
```

## POST /requests/{request_id}/assign

Asigna responsable, puede mover la solicitud a `IN_REVIEW`, registra historial
si cambia estado y registra auditoria administrativa.

Permiso requerido: `requests.manage`.

### Entrada

```json
{
  "assigned_to": "uuid",
  "comment": "string"
}
```

## POST /requests/{request_id}/observe

Cambia estado a `OBSERVED`, exige motivo, registra historial y auditoria.

Permiso requerido: `requests.manage`.

### Entrada

```json
{
  "reason": "string"
}
```

## POST /requests/{request_id}/approve

Cambia estado a `APPROVED`, registra `resolved_at`, historial y auditoria. No
aprueba solicitudes `CLOSED` o `REJECTED`.

Permiso requerido: `requests.manage`.

### Entrada opcional

```json
{
  "resolution": "string"
}
```

## POST /requests/{request_id}/reject

Cambia estado a `REJECTED`, exige motivo, registra `resolved_at`, historial y
auditoria.

Permiso requerido: `requests.manage`.

### Entrada

```json
{
  "reason": "string"
}
```

## POST /requests/{request_id}/close

Cambia estado a `CLOSED`, registra `closed_at`, historial y auditoria. En este
avance el cierre es administrativo.

Permiso requerido: `requests.manage`.

### Entrada opcional

```json
{
  "comment": "string"
}
```

## POST /requests/{request_id}/comments

Registra comentario en una solicitud. El usuario debe ser solicitante o tener
`requests.manage`. Los comentarios internos (`is_internal = true`) requieren
`requests.manage`.

Requiere bearer token valido.

### Entrada

```json
{
  "body": "string",
  "is_internal": false
}
```

### Salida

```json
{
  "data": {
    "id": "uuid",
    "request_id": "uuid",
    "author_id": "uuid",
    "author_name": "string",
    "body": "string",
    "is_internal": false,
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "message": "Comentario registrado",
  "errors": []
}
```

- `POST /requests/{request_id}/attachments`, `GET /requests/{request_id}/attachments`
  y descarga de adjuntos quedan formalizados en el modulo de documentos/archivos.

---

## 8. Documentos

Todas las respuestas JSON usan el envelope:

```json
{
  "data": {},
  "message": "OK",
  "errors": []
}
```

Las descargas exitosas responden archivo binario con `Content-Disposition`
seguro. Los errores de descarga mantienen el envelope estandar.

### 8.1 Politica inicial de archivos

- Tipos permitidos: PDF, PNG, JPG/JPEG, DOCX, XLSX y CSV.
- MIME permitidos: `application/pdf`, `image/png`, `image/jpeg`,
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`,
  `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` y
  `text/csv`.
- Tamano maximo: 10 MB por archivo.
- El backend sanitiza el nombre publico, almacena el archivo con clave interna
  UUID, calcula SHA-256 y no expone rutas fisicas ni `file_url`.
- Documentos generales se almacenan bajo separacion logica `public/documents`
  o `private/documents` segun estado/visibilidad inicial.
- Adjuntos de solicitudes se almacenan bajo `private/request-attachments`.

### 8.2 `GET /documents`

Publico. Lista solo documentos `PUBLISHED` con `visibility = PUBLIC` por
defecto.

Query params:

- `limit`: entero, 1 a 100, por defecto 20.
- `offset`: entero mayor o igual a 0, por defecto 0.
- `status`: `DRAFT`, `PUBLISHED` o `ARCHIVED`. Requiere `documents.manage`.
- `visibility`: `PUBLIC`, `AUTHENTICATED`, `BOARD` o `PRIVATE`. Requiere
  `documents.manage`.
- `category_id`: UUID. Requiere `documents.manage`.

### 8.3 `POST /documents`

Protegido con `documents.manage`.

Content-Type: `multipart/form-data`.

Campos:

- `file`: archivo obligatorio.
- `title`: texto obligatorio.
- `description`: texto opcional.
- `category_id`: UUID opcional.
- `visibility`: opcional, por defecto `PUBLIC`.
- `status`: opcional, por defecto `DRAFT`.

Reglas:

- valida extension, MIME, tamano y archivo no vacio;
- valida categoria activa si se informa;
- crea `documents` y version inicial en `document_versions`;
- calcula `sha256`;
- registra auditoria administrativa `document.created`.

### 8.4 `GET /documents/{document_id}`

Publico si el documento esta `PUBLISHED` y `PUBLIC`. Documentos privados,
borradores o archivados requieren `documents.manage`.

La respuesta no expone rutas internas ni `file_url`.

### 8.5 `GET /documents/{document_id}/download`

Descarga el archivo si el documento es publico (`PUBLISHED` + `PUBLIC`) o si el
usuario tiene `documents.manage`.

No acepta rutas de usuario; resuelve solo la clave interna persistida por el
backend.

### 8.6 `PATCH /documents/{document_id}`

Protegido con `documents.manage`.

Body JSON:

```json
{
  "title": "Acta actualizada",
  "description": "Texto opcional",
  "category_id": "uuid",
  "visibility": "PRIVATE",
  "status": "PUBLISHED"
}
```

Actualiza metadatos, valida categoria y registra auditoria
`document.updated`. Si `status` pasa a `PUBLISHED`, el backend asigna
`published_at` cuando no existe.

### 8.7 `DELETE /documents/{document_id}`

Protegido con `documents.manage`.

Realiza eliminacion logica: marca `status = ARCHIVED` y `deleted_at`. No borra
fisicamente el archivo en esta etapa. Registra auditoria `document.archived`.

### 8.8 Adjuntos de solicitudes

#### `POST /requests/{request_id}/attachments`

Requiere usuario autenticado. Permite adjuntar si el usuario es solicitante de
la solicitud o tiene `requests.manage`.

Content-Type: `multipart/form-data`.

Campos:

- `file`: archivo obligatorio.

Reglas:

- no permite adjuntar a solicitudes `CLOSED`, `APPROVED` o `REJECTED`;
- valida extension, MIME, tamano y archivo no vacio;
- crea registro en `request_attachments`;
- calcula SHA-256 en metadatos locales de almacenamiento;
- registra auditoria si la accion la realiza un usuario con `requests.manage`.

#### `GET /requests/{request_id}/attachments`

Requiere usuario autenticado. Lista adjuntos si el usuario es solicitante o
tiene `requests.manage`.

#### `GET /requests/{request_id}/attachments/{attachment_id}/download`

Requiere usuario autenticado. Descarga el adjunto si el usuario es solicitante
o tiene `requests.manage`.

---

## 9. Finanzas

Todos los montos se representan como decimales serializados en JSON sin usar
aritmetica de punto flotante.

Visibilidad inicial:

- presupuestos `ACTIVE` y `CLOSED` son publicos;
- ingresos y gastos `APPROVED` son publicos;
- usuarios con `finances.manage` pueden consultar todos los estados;
- filtros que soliciten estados no publicos requieren sesion activa y
  `finances.manage`.

### GET /finances/budgets

Lista presupuestos con paginacion `limit` y `offset`.

Filtro opcional: `status`.

El usuario publico recibe solo presupuestos `ACTIVE` o `CLOSED`. Un usuario con
`finances.manage` recibe todos los estados si no indica filtro.

### POST /finances/budgets

Requiere `finances.manage`. Crea un presupuesto en estado `DRAFT` y registra
auditoria `finance.budget.created`.

```json
{
  "student_center_id": "uuid | null",
  "name": "Presupuesto 2026",
  "period_start": "2026-01-01",
  "period_end": "2026-12-31",
  "total_amount": "5000000.00"
}
```

El nombre es obligatorio, `period_end >= period_start`, `total_amount >= 0` y
el centro de estudiantes informado debe existir y estar activo.

### GET /finances/budgets/{budget_id}

El detalle es publico para estados `ACTIVE` y `CLOSED`. Los estados `DRAFT` y
`ARCHIVED` requieren `finances.manage`.

### PATCH /finances/budgets/{budget_id}

Requiere `finances.manage`. Actualiza metadatos o estado y registra auditoria
`finance.budget.updated`.

Transiciones iniciales:

- `DRAFT -> ACTIVE | ARCHIVED`;
- `ACTIVE -> CLOSED | ARCHIVED`;
- `CLOSED -> ARCHIVED`;
- `ARCHIVED` no es editable.

### GET /finances/income

Lista ingresos con paginacion. Admite filtros `status` y `budget_id`.
Publicamente retorna solo ingresos `APPROVED`; `finances.manage` permite
consultar todos.

### POST /finances/income

Requiere `finances.manage`. Registra un ingreso como `APPROVED`, porque el flujo
MVP no define una aprobacion separada de ingresos. Registra auditoria
`finance.income.created`.

```json
{
  "budget_id": "uuid | null",
  "amount": "1500.00",
  "source": "Aporte estudiantil",
  "description": "string | null",
  "received_on": "2026-06-24"
}
```

El monto debe ser positivo y el presupuesto informado debe existir y no estar
archivado.

### GET /finances/expenses

Lista gastos con paginacion. Admite filtros `status`, `budget_id` y
`category_id`. Publicamente retorna solo gastos `APPROVED`;
`finances.manage` permite consultar todos.

### POST /finances/expenses

Requiere `finances.manage`. Crea un gasto en estado `PENDING` y registra
auditoria `finance.expense.created`.

```json
{
  "budget_id": "uuid | null",
  "category_id": "uuid | null",
  "amount": "500.00",
  "description": "Compra de materiales",
  "spent_on": "2026-06-24",
  "receipt_document_id": "uuid"
}
```

El monto debe ser positivo. Presupuesto y categoria, si se informan, deben
existir. `receipt_document_id` debe corresponder a un documento no eliminado,
no archivado y con una version. El backend persiste como `receipt_url` la ruta
canonica `/api/v1/documents/{document_id}/download`; su descarga conserva las
reglas de visibilidad del modulo documental.

### PATCH /finances/expenses/{expense_id}

Requiere `finances.manage`. Solo modifica gastos `PENDING` y registra auditoria
`finance.expense.updated`.

### POST /finances/expenses/{expense_id}/approve

Requiere `finances.manage`. Cambia un gasto `PENDING` a `APPROVED` y registra
auditoria `finance.expense.approved`. Un gasto aprobado, rechazado o anulado no
puede aprobarse ni editarse mediante estos endpoints.

### GET /finances/summary

Retorna totales de ingresos, gastos, balance y gastos agrupados por categoria.
El resumen publico considera solo registros `APPROVED`. Con
`finances.manage`, el resumen operativo incluye `PENDING` y `APPROVED`,
excluyendo `REJECTED` y `VOID`.

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
- almacenamiento externo de archivos;
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
- `GET /api/v1/documents`
- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/download`
- `PATCH /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/requests/{request_id}/attachments`
- `GET /api/v1/requests/{request_id}/attachments`
- `GET /api/v1/requests/{request_id}/attachments/{attachment_id}/download`
- `GET /api/v1/finances/budgets`
- `POST /api/v1/finances/budgets`
- `GET /api/v1/finances/budgets/{budget_id}`
- `PATCH /api/v1/finances/budgets/{budget_id}`
- `GET /api/v1/finances/income`
- `POST /api/v1/finances/income`
- `GET /api/v1/finances/expenses`
- `POST /api/v1/finances/expenses`
- `PATCH /api/v1/finances/expenses/{expense_id}`
- `POST /api/v1/finances/expenses/{expense_id}/approve`
- `GET /api/v1/finances/summary`

La validacion real de Google requiere configurar `CEE_GOOGLE_CLIENT_ID`.
El dominio institucional puede restringirse con
`CEE_INSTITUTIONAL_EMAIL_DOMAIN`.
