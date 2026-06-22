# CHECKLIST_VALIDACION.md

# Checklist de validación — CEE Conecta

## 1. Fábrica agéntica

- [ ] Existe estructura `factory/`.
- [ ] Existe CLI de fábrica.
- [ ] Existe `init-project`.
- [ ] Existe `run`.
- [ ] Existe `verify`.
- [ ] Existen agentes registrados.
- [ ] Existe arnés.
- [ ] Existe orquestador.
- [ ] Existen validadores.
- [ ] Se generan runs.
- [ ] Se generan artefactos.
- [ ] Existe reporte final.
- [ ] Los tests de fábrica pasan.

---

## 2. Documentación de coordinación

- [ ] Existe `docs/PROJECT_CONTEXT.md`.
- [ ] Existe `docs/AGENT_PROTOCOL.md`.
- [ ] Existe `docs/DECISIONS.md`.
- [ ] Existe `docs/HANDOFFS.md`.
- [ ] Existe `docs/API_CONTRACT.md`.
- [ ] Existe `docs/DATABASE_MODEL.md`.
- [ ] Existe `docs/UI_MAP.md`.

---

## 3. Base de datos

- [ ] Existe `schema.sql`.
- [ ] Existen tablas principales.
- [ ] Existen claves primarias.
- [ ] Existen claves foráneas.
- [ ] Existen constraints.
- [ ] Existen índices.
- [ ] Existe seed de roles.
- [ ] Existe documentación del modelo.

---

## 4. Backend

- [ ] Existe API FastAPI.
- [ ] Existe estructura modular.
- [ ] Existe autenticación Google.
- [ ] Existen roles.
- [ ] Existen endpoints principales.
- [ ] Existe validación de entrada.
- [ ] Existe autorización por rol.
- [ ] Existe documentación OpenAPI.
- [ ] Existen pruebas backend.

---

## 5. Frontend

- [ ] Existe proyecto React.
- [ ] Existen rutas públicas.
- [ ] Existen rutas privadas.
- [ ] Existe login.
- [ ] Existe dashboard estudiante.
- [ ] Existe dashboard admin.
- [ ] Existen formularios principales.
- [ ] Existe integración API.
- [ ] Existen validaciones visuales.

---

## 6. Seguridad

- [ ] No se almacenan contraseñas.
- [ ] No hay secretos en repositorio.
- [ ] Rutas privadas protegidas.
- [ ] Endpoints administrativos protegidos.
- [ ] Archivos validados.
- [ ] Auditoría de acciones críticas.
- [ ] Tokens manejados de forma segura.

---

## 7. Producto

- [ ] Noticias funcionales.
- [ ] Eventos funcionales.
- [ ] Solicitudes funcionales.
- [ ] Documentos funcionales.
- [ ] Finanzas básicas funcionales.
- [ ] Roles funcionales.
- [ ] Auditoría funcional.

---

## 8. Cierre técnico

- [ ] Existe reporte de pruebas.
- [ ] Existe matriz de trazabilidad.
- [ ] Existe manual técnico.
- [ ] Existe manual de usuario.
- [ ] Existe informe de cierre.
- [ ] Existe evidencia de fábrica.

---

## 9. QA usuarios, roles y permisos

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_auth_users_permissions

- [x] `GET /api/v1/users/me` requiere autenticacion valida.
- [x] `GET /api/v1/users` requiere `users.manage`.
- [x] `GET /api/v1/users/{user_id}` requiere `users.manage`.
- [x] `PATCH /api/v1/users/{user_id}/status` requiere `users.manage`.
- [x] `GET /api/v1/roles` requiere `roles.manage`.
- [x] `GET /api/v1/permissions` requiere `roles.manage`.
- [x] Usuario sin permiso recibe `403`.
- [x] Usuario sin sesion activa recibe `401`.
- [x] Sesion revocada o expirada no puede operar.
- [x] Usuario inactivo no puede operar.
- [x] No existe bypass por rol `ADMIN` sin permiso explicito.
- [x] Respuestas revisadas usan envelope `{ data, message, errors }`.
- [x] Cambio efectivo de estado de usuario genera auditoria administrativa.
- [ ] Auditoria persistida validada contra PostgreSQL real.
- [ ] Semantica de auditoria para PATCH idempotente definida.

**Resultado:** aprobado para avanzar a noticias/comunicados con observaciones
menores registradas en `docs/QA_REPORT.md`.

---

## 10. QA noticias y comunicados

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_news_announcements

- [x] `GET /api/v1/news` lista solo `PUBLISHED` por defecto.
- [x] `GET /api/v1/announcements` lista solo `PUBLISHED` por defecto.
- [x] Detalle publico de noticia no expone `DRAFT`.
- [x] Detalle publico de noticia no expone `ARCHIVED`.
- [x] Filtros administrativos de noticias para `DRAFT` o `ARCHIVED` requieren `content.publish`.
- [x] `POST /api/v1/news` requiere sesion y `content.publish`.
- [x] `PATCH /api/v1/news/{news_id}` requiere sesion y `content.publish`.
- [x] `DELETE /api/v1/news/{news_id}` requiere sesion y `content.publish`.
- [x] `POST /api/v1/news/{news_id}/publish` requiere sesion y `content.publish`.
- [x] `POST /api/v1/announcements` requiere sesion y `content.publish`.
- [x] `PATCH /api/v1/announcements/{announcement_id}` requiere sesion y `content.publish`.
- [x] `POST /api/v1/announcements/{announcement_id}/publish` requiere sesion y `content.publish`.
- [x] Usuario con permiso puede crear, actualizar, archivar y publicar noticias.
- [x] Usuario con permiso puede crear, actualizar y publicar comunicados.
- [x] Publicar asigna estado `PUBLISHED` y `published_at`.
- [x] Archivar noticia conserva el registro y cambia estado a `ARCHIVED`.
- [x] Acciones mutantes generan auditoria administrativa a nivel de servicio.
- [x] No se permite crear ni publicar contenido vacio.
- [x] Respuestas revisadas usan envelope `{ data, message, errors }`.
- [ ] Respuesta de `DELETE /api/v1/news/{news_id}` alineada estrictamente con ejemplo contractual `{ id, status }`.
- [ ] Auditoria persistida validada contra PostgreSQL real.
- [ ] Semantica de auditoria para mutaciones idempotentes definida.

**Resultado:** aprobado para avanzar a eventos con observaciones menores
registradas en `docs/QA_REPORT.md`.
