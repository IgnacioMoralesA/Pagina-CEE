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
**Estado:** pendiente  

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
**Estado:** pendiente  

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
