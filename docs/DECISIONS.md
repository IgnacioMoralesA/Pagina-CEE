# DECISIONS.md

# Registro de decisiones técnicas

## Propósito

Este archivo registra decisiones que afectan al proyecto CEE Conecta.

Toda decisión debe tener:

- fecha;
- agente;
- contexto;
- decisión;
- justificación;
- impacto;
- estado.

---

## Estados permitidos

- `propuesta`
- `aprobada`
- `rechazada`
- `reemplazada`

---

## DEC-001 — Producto final sin agentes internos obligatorios

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Contexto

El curso exige usar una fábrica agéntica para desarrollar el proyecto, pero no obliga a que el producto final incorpore agentes de IA como funcionalidad visible.

### Decisión

CEE Conecta será una aplicación web tradicional. La fábrica agéntica será el proceso de desarrollo y generación de evidencia.

### Justificación

Esto evita sobredimensionar el producto y alinea el trabajo con la evaluación: entrada clara, refinamiento, planificación, agentes, workflows, arnés, validación, evidencia y cierre técnico.

### Impacto

El backend, frontend y base de datos no necesitan implementar lógica agéntica interna en el MVP.

---

## DEC-002 — Stack inicial

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

Usar:

- FastAPI para backend.
- React + Vite para frontend.
- PostgreSQL como base de datos.
- Pytest para pruebas backend y de fábrica.
- OpenAPI / Swagger para documentación API.

### Justificación

Es un stack rápido de desarrollar, claro para separar módulos y adecuado para una API REST.

### Impacto

Los agentes deben generar artefactos compatibles con este stack.

---

## DEC-003 — Autenticación institucional con Google

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

El sistema usará Google OAuth / OpenID Connect para autenticación con correo institucional.

### Justificación

Permite evitar almacenamiento de contraseñas y delegar identidad a Google.

### Impacto

La base de datos debe almacenar, como mínimo:

- identificador externo de Google;
- correo;
- nombre;
- rol;
- estado;
- último acceso.

---

## DEC-004 — Separación por hilos de trabajo

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

El trabajo se dividirá en hilos por agente:

- base de datos;
- backend;
- frontend;
- QA;
- seguridad;
- documentación.

### Justificación

Permite mantener foco, trazabilidad y responsabilidades claras.

### Impacto

Cada agente debe declarar su identidad y respetar el protocolo de trabajo definido en `docs/AGENT_PROTOCOL.md`.

---

## DEC-005 — Fuente de verdad documental

**Fecha:** 2026-06-18  
**Agente:** agent.product_owner  
**Estado:** aprobada  

### Decisión

Los documentos de coordinación serán fuente de verdad:

- `docs/PROJECT_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/API_CONTRACT.md`
- `docs/DATABASE_MODEL.md`
- `docs/UI_MAP.md`
- `docs/HANDOFFS.md`

### Justificación

Evita inconsistencias entre agentes.

### Impacto

Todo cambio transversal debe actualizar documentos.
