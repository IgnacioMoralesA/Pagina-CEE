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
    "user": {
      "id": "uuid",
      "email": "string",
      "name": "string",
      "role": "STUDENT"
    }
  },
  "message": "Login correcto",
  "errors": []
}
```

---

## GET /users/me

Retorna el usuario autenticado.

---

## 4. Noticias

- `GET /news`
- `POST /news`
- `GET /news/{news_id}`
- `PATCH /news/{news_id}`
- `DELETE /news/{news_id}`
- `POST /news/{news_id}/publish`

---

## 5. Comunicados

- `GET /announcements`
- `POST /announcements`
- `PATCH /announcements/{announcement_id}`
- `POST /announcements/{announcement_id}/publish`

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
