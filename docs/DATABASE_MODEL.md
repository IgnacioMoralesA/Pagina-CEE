# DATABASE_MODEL.md

# Modelo de datos inicial — CEE Conecta

## 1. Propósito

Este documento define el modelo de datos inicial de CEE Conecta.

El agente de base de datos debe completar y formalizar este diseño en `app/database/schema.sql`.

---

## 2. Convenciones

- PostgreSQL.
- Tablas en plural.
- Clave primaria: `id UUID PRIMARY KEY`.
- Fechas: `created_at`, `updated_at`.
- Eliminación lógica: `deleted_at`.
- Relaciones mediante claves foráneas.
- Estados mediante `VARCHAR` o tipos ENUM según decisión del agente de base de datos.

---

## 3. Tablas iniciales

## Seguridad y usuarios

1. `users`
2. `roles`
3. `permissions`
4. `role_permissions`
5. `user_roles`
6. `sessions`
7. `auth_events`

## Centro de estudiantes

8. `student_centers`
9. `board_periods`
10. `board_members`
11. `positions`

## Publicaciones

12. `publication_categories`
13. `news`
14. `announcements`
15. `publication_attachments`

## Eventos

16. `event_categories`
17. `events`
18. `event_registrations`
19. `event_attendance`

## Solicitudes

20. `request_categories`
21. `requests`
22. `request_status_history`
23. `request_comments`
24. `request_attachments`

## Reuniones

25. `meetings`
26. `meeting_participants`
27. `meeting_minutes`
28. `agreements`
29. `agreement_tasks`

## Finanzas

30. `budgets`
31. `budget_items`
32. `income_records`
33. `expense_categories`
34. `expense_records`
35. `financial_documents`

## Inventario

36. `inventory_categories`
37. `inventory_items`
38. `inventory_movements`
39. `resource_loans`
40. `resource_returns`

## Documentos

41. `document_categories`
42. `documents`
43. `document_versions`

## Participación

44. `surveys`
45. `survey_questions`
46. `survey_options`
47. `survey_responses`
48. `votings`
49. `voting_options`
50. `eligible_voters`
51. `votes`

## Sistema

52. `audit_events`
53. `notifications`

---

## 4. Entidades clave

## users

Debe almacenar:

- `id`
- `google_sub`
- `email`
- `name`
- `avatar_url`
- `status`
- `last_login_at`
- `created_at`
- `updated_at`
- `deleted_at`

Reglas:

- `google_sub` único.
- `email` único.
- No almacenar contraseñas.

---

## news

Debe almacenar:

- título;
- resumen;
- contenido;
- autor;
- categoría;
- estado;
- fecha de publicación;
- imagen opcional.

Estados:

- `DRAFT`
- `PUBLISHED`
- `ARCHIVED`

---

## events

Debe almacenar:

- nombre;
- descripción;
- fecha inicio;
- fecha término;
- lugar;
- cupos;
- responsable;
- estado.

Estados:

- `PLANNED`
- `PUBLISHED`
- `FINISHED`
- `CANCELLED`

---

## requests

Debe almacenar:

- solicitante;
- categoría;
- título;
- descripción;
- estado;
- prioridad;
- responsable;
- resolución.

Estados:

- `SUBMITTED`
- `IN_REVIEW`
- `OBSERVED`
- `APPROVED`
- `REJECTED`
- `CLOSED`

---

## expense_records

Debe almacenar:

- presupuesto asociado;
- categoría;
- monto;
- descripción;
- fecha;
- responsable;
- comprobante;
- estado.

---

## inventory_items

Debe almacenar:

- nombre;
- código;
- categoría;
- descripción;
- estado físico;
- disponibilidad;
- cantidad.

---

## votings

Debe almacenar:

- título;
- descripción;
- fecha de apertura;
- fecha de cierre;
- estado;
- configuración de anonimato.

---

## 5. Reglas de integridad iniciales

- Todo usuario debe tener correo único.
- Todo evento debe tener fecha de término posterior a inicio.
- Toda inscripción debe ser única por usuario y evento.
- Toda solicitud debe tener solicitante.
- Todo gasto debe tener monto positivo.
- Todo recurso prestado debe estar disponible.
- Todo voto debe ser único por usuario y votación.
- Toda publicación pública debe tener fecha de publicación.
- Toda acción administrativa debe generar auditoría.

---

## 6. Pendientes del agente de base de datos

El agente `agent.database_designer` debe:

1. Convertir este modelo en SQL real.
2. Definir tipos de datos.
3. Definir índices.
4. Definir constraints.
5. Crear seed inicial de roles.
6. Crear documentación actualizada.
7. Registrar decisiones en `docs/DECISIONS.md`.
8. Dejar handoff para backend.

---

## 7. Avance SQL inicial

**Fecha:** 2026-06-21
**Agente:** `agent.database_designer`

Artefactos creados:

- `app/database/schema.sql`
- `app/database/seed.sql`

### Checklist solicitada

- [x] Tablas principales creadas
- [x] Claves primarias definidas
- [x] Claves foraneas definidas
- [x] Constraints CHECK
- [x] Indices importantes
- [x] Seed de roles iniciales
- [x] Estados definidos para noticias, eventos, solicitudes, recursos y votaciones
- [x] Decisiones registradas en DECISIONS.md
- [x] Handoff hacia backend_developer

### Criterios aplicados

- Las claves primarias usan `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- Los estados principales se definen con tipos ENUM de PostgreSQL.
- Las tablas de negocio incluyen `created_at`, `updated_at` y `deleted_at` cuando aplica eliminacion logica.
- Las reglas de integridad iniciales se cubren con claves unicas, claves foraneas, `CHECK` e indices parciales donde corresponde.
- El seed inicial incluye roles, permisos base y catalogos minimos para iniciar el MVP.

### Estados definidos

- Noticias y comunicados: `DRAFT`, `PUBLISHED`, `ARCHIVED`.
- Eventos: `PLANNED`, `PUBLISHED`, `FINISHED`, `CANCELLED`.
- Solicitudes: `SUBMITTED`, `IN_REVIEW`, `OBSERVED`, `APPROVED`, `REJECTED`, `CLOSED`.
- Recursos: `AVAILABLE`, `LOANED`, `DAMAGED`, `LOST`, `RETIRED`.
- Votaciones: `DRAFT`, `OPEN`, `CLOSED`, `CANCELLED`.
