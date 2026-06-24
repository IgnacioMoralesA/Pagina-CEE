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

---

## 11. QA eventos, inscripciones y asistencia

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_events

- [x] `GET /api/v1/events` lista solo eventos `PUBLISHED` proximos por defecto.
- [x] `GET /api/v1/events` no expone `PLANNED`, `CANCELLED` ni `FINISHED` publicamente.
- [x] `GET /api/v1/events/{event_id}` no expone eventos no publicos a usuarios sin permisos.
- [x] Filtros administrativos de estados no publicos requieren `events.manage`.
- [x] `POST /api/v1/events` requiere sesion y `events.manage`.
- [x] `PATCH /api/v1/events/{event_id}` requiere sesion y `events.manage`.
- [x] `POST /api/v1/events/{event_id}/publish` requiere sesion y `events.manage`.
- [x] `POST /api/v1/events/{event_id}/cancel` requiere sesion y `events.manage`.
- [x] `POST /api/v1/events/{event_id}/finish` requiere sesion y `events.manage`.
- [x] `POST /api/v1/events/{event_id}/attendance` requiere sesion y `events.manage`.
- [x] Inscripcion y cancelacion de inscripcion requieren usuario autenticado.
- [x] Usuario con permiso puede crear, actualizar, publicar, cancelar y finalizar eventos.
- [x] Usuario con permiso puede registrar asistencia.
- [x] Crear, actualizar, publicar, cancelar, finalizar y registrar asistencia generan auditoria administrativa a nivel de servicio.
- [x] Motivo de cancelacion queda en metadata de auditoria.
- [x] Fecha de termino anterior o igual a inicio se rechaza al crear y actualizar.
- [x] Capacidad del evento se respeta al registrar usuarios.
- [x] No se permite inscripcion duplicada.
- [x] No se permite inscripcion a eventos no publicados.
- [x] Usuario autenticado puede cancelar su propia inscripcion.
- [x] Cancelacion de inscripcion propia no afecta a otros usuarios.
- [x] Asistencia requiere inscripcion previa.
- [x] Respuestas revisadas usan envelope `{ data, message, errors }`.
- [ ] Auditoria persistida validada contra PostgreSQL real.
- [ ] Semantica de auditoria para mutaciones idempotentes definida.

**Resultado:** aprobado para avanzar a solicitudes estudiantiles con
observaciones menores registradas en `docs/QA_REPORT.md`.

---

## 12. QA solicitudes estudiantiles

**Fecha:** 2026-06-22  
**Agente:** agent.qa_engineer  
**Fase:** qa_requests

- [x] `GET /api/v1/requests` coincide con `docs/API_CONTRACT.md`.
- [x] `POST /api/v1/requests` coincide con `docs/API_CONTRACT.md`.
- [x] `GET /api/v1/requests/{request_id}` coincide con `docs/API_CONTRACT.md`.
- [x] `PATCH /api/v1/requests/{request_id}` coincide con `docs/API_CONTRACT.md`.
- [x] Endpoints administrativos `assign`, `observe`, `approve`, `reject` y `close` coinciden con `docs/API_CONTRACT.md`.
- [x] Comentarios de solicitudes coinciden con `docs/API_CONTRACT.md`.
- [x] Estudiante puede crear solicitud con `requests.create`.
- [x] Solicitud creada queda en estado `SUBMITTED`.
- [x] Crear solicitud genera historial inicial.
- [x] Estudiante lista solo solicitudes propias.
- [x] Estudiante no puede ver solicitud ajena.
- [x] Usuario sin sesion no puede crear solicitudes.
- [x] Usuario sin `requests.create` no puede crear solicitudes.
- [x] Usuario sin `requests.manage` no puede listar todas las solicitudes.
- [x] Usuario sin `requests.manage` no puede usar filtros administrativos.
- [x] Usuario con `requests.manage` puede listar todas las solicitudes.
- [x] Usuario con `requests.manage` puede filtrar por estado y categoria.
- [x] Estudiante puede editar solicitud propia en `SUBMITTED`.
- [x] Estudiante puede editar solicitud propia en `OBSERVED`.
- [x] Estudiante no puede editar solicitudes `CLOSED`, `APPROVED` o `REJECTED`.
- [x] Estudiante no puede editar campos administrativos.
- [x] Usuario administrativo puede actualizar campos administrativos con auditoria.
- [x] Usuario administrativo puede asignar responsable.
- [x] Asignar responsable genera auditoria e historial si cambia estado.
- [x] Observar solicitud exige motivo.
- [x] Observar cambia estado a `OBSERVED` y genera historial.
- [x] Aprobar cambia estado a `APPROVED` y genera historial/auditoria.
- [x] Rechazar exige motivo y genera historial/auditoria.
- [x] No se puede aprobar una solicitud `CLOSED`.
- [x] No se puede aprobar una solicitud `REJECTED`.
- [x] Cerrar cambia estado a `CLOSED` bajo regla administrativa de `DEC-013`.
- [x] Acciones administrativas devuelven `401` sin sesion.
- [x] Acciones administrativas devuelven `403` sin `requests.manage`.
- [x] Comentarios solo pueden ser creados por dueno de solicitud o administrador.
- [x] Comentarios internos requieren `requests.manage`.
- [x] Comentarios internos no se exponen al solicitante.
- [x] Respuestas revisadas usan envelope `{ data, message, errors }`.
- [ ] Auditoria persistida validada contra PostgreSQL real.
- [ ] Semantica idempotente de acciones administrativas definida.

**Resultado:** aprobado para avanzar a documentos/archivos con observaciones
menores registradas en `docs/QA_REPORT.md`.

---

## 13. QA documentos, archivos y adjuntos

**Fecha:** 2026-06-24
**Agente:** agent.qa_engineer
**Fase:** qa_documents_files

- [x] Los nueve endpoints coinciden con `docs/API_CONTRACT.md`.
- [x] `GET /api/v1/documents` lista publicamente solo documentos `PUBLISHED` y `PUBLIC`.
- [x] Documentos privados o borradores no son visibles publicamente.
- [x] Documentos privados no pueden descargarse sin `documents.manage`.
- [x] Usuario con `documents.manage` puede subir documentos.
- [x] La subida calcula SHA-256.
- [x] La subida usa un nombre interno UUID unico.
- [x] La respuesta no expone `storage_key`, `file_url` ni rutas fisicas.
- [x] Archivos vacios son rechazados.
- [x] Archivos mayores al limite son rechazados.
- [x] El limite se aplica aun sin `Content-Length`.
- [x] Extensiones o MIME no permitidos son rechazados.
- [x] Ejecutables renombrados son rechazados.
- [x] PDF valido es aceptado.
- [x] PNG valido es aceptado.
- [x] JPEG valido es aceptado.
- [x] DOCX valido es aceptado.
- [x] XLSX valido es aceptado.
- [x] CSV UTF-8 valido es aceptado.
- [x] Nombres con rutas maliciosas son sanitizados y no alteran el almacenamiento.
- [x] `POST`, `PATCH` y `DELETE /documents` devuelven `401` sin sesion.
- [x] `POST`, `PATCH` y `DELETE /documents` devuelven `403` sin `documents.manage`.
- [x] Filtros administrativos requieren `documents.manage`.
- [x] `PATCH` actualiza metadatos y registra auditoria.
- [x] Publicar mediante `PATCH` asigna `published_at`.
- [x] Categoria inexistente o inactiva es rechazada.
- [x] `DELETE` realiza eliminacion logica.
- [x] Documentos eliminados no aparecen en listados publicos.
- [x] Crear, actualizar y archivar documentos generan auditoria administrativa.
- [x] Dueno de solicitud puede adjuntar archivos.
- [x] Usuario ajeno no puede adjuntar a una solicitud de otro usuario.
- [x] `requests.manage` permite adjuntar administrativamente.
- [x] Solicitudes `CLOSED`, `APPROVED` o `REJECTED` no aceptan adjuntos.
- [x] Dueno puede listar y descargar adjuntos.
- [x] Usuario ajeno no puede listar ni descargar adjuntos.
- [x] `requests.manage` permite listar y descargar adjuntos.
- [x] Subida, listado y descarga de adjuntos requieren sesion.
- [x] Carga administrativa de adjuntos genera auditoria.
- [x] Respuestas JSON revisadas usan envelope `{ data, message, errors }`.
- [x] Descargas exitosas son binarias y usan nombre publico sanitizado.
- [ ] Auditoria, archivado y metadatos persistidos validados contra PostgreSQL real.
- [ ] Parser multipart local reemplazado por libreria mantenida.
- [ ] Cuarentena y escaneo antimalware implementados.
- [ ] CSV injection neutralizada o rechazada.
- [ ] Almacenamiento de produccion validado como privado y aislado.
- [ ] SHA-256 verificado en descarga y limpieza de huerfanos definida.

**Resultado:** aprobado funcionalmente para avanzar a finanzas basicas. El
hardening pendiente no bloquea el desarrollo siguiente, pero bloquea cargas no
confiables en produccion.
