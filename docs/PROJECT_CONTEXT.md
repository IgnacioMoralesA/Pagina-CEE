# PROJECT_CONTEXT.md

# CEE Conecta — Contexto maestro del proyecto

## 1. Propósito

Este archivo es la fuente de verdad compartida para todos los hilos de trabajo del proyecto CEE Conecta.

Todo agente debe leer este documento antes de modificar archivos. Si una decisión contradice este contexto, debe registrarse primero en `docs/DECISIONS.md` y dejarse un handoff en `docs/HANDOFFS.md`.

---

## 2. Nombre del proyecto

CEE Conecta

---

## 3. Descripción breve

CEE Conecta es una plataforma web para centralizar la gestión de un Centro de Estudiantes universitario.

El sistema permitirá administrar información pública, noticias, comunicados, eventos, solicitudes estudiantiles, documentos, actas, finanzas básicas, inventario, encuestas, votaciones, usuarios, roles y transparencia.

---

## 4. Interpretación correcta de la fábrica agéntica

La fábrica agéntica se utiliza como proceso de desarrollo del proyecto.

El producto final no necesita tener agentes de IA internos.

El proyecto debe demostrar que CEE Conecta fue construido mediante una fábrica controlada con:

- entrada clara;
- refinamiento;
- planificación;
- agentes especializados;
- workflows;
- arnés;
- ejecución reproducible;
- validación;
- evidencia;
- cierre técnico.

---

## 5. Producto final esperado

Una aplicación web funcional compuesta por:

- frontend;
- backend;
- base de datos;
- autenticación institucional;
- API REST;
- pruebas;
- documentación;
- evidencia técnica.

---

## 6. Stack tecnológico aprobado

## Frontend

React con Vite.

## Backend

FastAPI con Python.

## Base de datos

PostgreSQL.

## Autenticación

Google OAuth / OpenID Connect con correo institucional.

## Testing

- Pytest para backend y fábrica.
- Vitest o Playwright para frontend cuando corresponda.

## Documentación API

OpenAPI / Swagger.

---

## 7. Roles del sistema

Roles iniciales:

- `STUDENT`: estudiante autenticado.
- `BOARD_MEMBER`: integrante general de la directiva.
- `PRESIDENT`: presidente del CEE.
- `TREASURER`: tesorero.
- `SECRETARY`: secretario.
- `ADMIN`: administrador del sistema.

---

## 8. Módulos principales

1. Autenticación y usuarios.
2. Roles y permisos.
3. Página pública.
4. Noticias y comunicados.
5. Eventos.
6. Solicitudes estudiantiles.
7. Reuniones, actas y acuerdos.
8. Finanzas y transparencia.
9. Inventario y préstamos.
10. Documentos.
11. Encuestas.
12. Votaciones.
13. Auditoría.
14. Reportes.
15. Administración.

---

## 9. Módulos prioritarios para MVP

El primer MVP debe incluir:

1. Login institucional con Google.
2. Usuarios y roles.
3. Noticias.
4. Eventos.
5. Solicitudes estudiantiles.
6. Documentos.
7. Finanzas básicas.
8. Auditoría.

Módulos extendidos:

- inventario;
- reuniones y actas;
- encuestas;
- votaciones;
- transparencia avanzada;
- reportes.

---

## 10. Reglas globales

- El sistema no almacena contraseñas de usuarios.
- El login se realiza con cuenta institucional de Google.
- Toda acción administrativa debe quedar en auditoría.
- Los usuarios sin rol administrativo no pueden crear contenido público.
- Los estudiantes pueden consultar información pública y crear solicitudes.
- Las publicaciones deben tener estado.
- Las solicitudes deben tener historial de estado.
- Los gastos deben tener comprobante.
- Un usuario no puede votar dos veces en la misma votación.
- Una solicitud cerrada no puede modificarse.
- Un recurso prestado no puede prestarse nuevamente hasta su devolución.

---

## 11. Estados principales

## Publicaciones

- `DRAFT`
- `PUBLISHED`
- `ARCHIVED`

## Eventos

- `PLANNED`
- `PUBLISHED`
- `FINISHED`
- `CANCELLED`

## Solicitudes

- `SUBMITTED`
- `IN_REVIEW`
- `OBSERVED`
- `APPROVED`
- `REJECTED`
- `CLOSED`

## Recursos

- `AVAILABLE`
- `LOANED`
- `DAMAGED`
- `LOST`
- `RETIRED`

## Votaciones

- `DRAFT`
- `OPEN`
- `CLOSED`
- `CANCELLED`

---

## 12. Convenciones de nombres

## Backend

- Rutas API bajo `/api/v1`.
- Nombres de archivos en `snake_case`.
- Entidades y modelos en singular.
- Tablas en plural.
- Servicios con sufijo `_service`.

## Frontend

- Componentes en `PascalCase`.
- Hooks con prefijo `use`.
- Rutas en minúscula.
- Servicios API en `src/services`.

## Base de datos

- Tablas en plural.
- Columnas en `snake_case`.
- Claves primarias llamadas `id`.
- Fechas estándar: `created_at`, `updated_at`.
- Eliminación lógica mediante `deleted_at` cuando corresponda.

---

## 13. Archivos de coordinación obligatorios

- `docs/PROJECT_CONTEXT.md`
- `docs/AGENT_PROTOCOL.md`
- `docs/DECISIONS.md`
- `docs/HANDOFFS.md`
- `docs/API_CONTRACT.md`
- `docs/DATABASE_MODEL.md`
- `docs/UI_MAP.md`

---

## 14. Regla de consistencia

Ningún agente debe inventar endpoints, tablas, pantallas, reglas o roles si ya existen definidos en estos documentos.

Si necesita agregar algo, debe:

1. registrar la decisión en `docs/DECISIONS.md`;
2. dejar handoff para los agentes afectados en `docs/HANDOFFS.md`;
3. actualizar el documento correspondiente;
4. explicar el impacto.

---

## 15. Orden recomendado de trabajo

1. Base de datos.
2. Contrato API.
3. Backend.
4. Frontend.
5. QA.
6. Seguridad.
7. Documentación.
8. Cierre técnico.

---

## 16. Agentes de trabajo por hilo

- Hilo de base de datos: `agent.database_designer`
- Hilo backend: `agent.backend_developer`
- Hilo frontend: `agent.frontend_developer`
- Hilo QA: `agent.qa_engineer`
- Hilo seguridad: `agent.security_reviewer`
- Hilo documentación: `agent.documenter`

---

## 17. Restricciones

- No modificar archivos fuera del alcance del agente sin autorización.
- No cambiar decisiones ya registradas sin nueva decisión.
- No romper contratos compartidos.
- No implementar backend antes de tener modelo de datos base.
- No implementar frontend inventando endpoints.
- No eliminar evidencia de fábrica.
- No guardar secretos en el repositorio.
