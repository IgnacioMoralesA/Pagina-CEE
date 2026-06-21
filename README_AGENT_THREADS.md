# README_AGENT_THREADS.md

# Cómo trabajar CEE Conecta en hilos separados

## 1. Idea

El proyecto se trabajará en hilos separados, cada uno representando a un agente de la fábrica.

Cada hilo debe mantener consistencia con los documentos de coordinación ubicados en `docs/`.

---

## 2. Hilos recomendados

## Hilo 1 — Base de datos

Agente activo:

```text
agent.database_designer
```

Objetivo:

Diseñar e implementar modelo de datos PostgreSQL.

---

## Hilo 2 — Backend

Agente activo:

```text
agent.backend_developer
```

Objetivo:

Implementar API REST FastAPI.

---

## Hilo 3 — Frontend

Agente activo:

```text
agent.frontend_developer
```

Objetivo:

Implementar interfaz React.

---

## Hilo 4 — QA

Agente activo:

```text
agent.qa_engineer
```

Objetivo:

Validar pruebas, cobertura y completitud.

---

## Hilo 5 — Seguridad

Agente activo:

```text
agent.security_reviewer
```

Objetivo:

Revisar autenticación, autorización y exposición de datos.

---

## Hilo 6 — Documentación

Agente activo:

```text
agent.documenter
```

Objetivo:

Mantener documentación y cierre técnico.

---

## 3. Prompt base para iniciar un hilo

```text
Estamos trabajando en el proyecto CEE Conecta.

Este hilo corresponde exclusivamente al agente:

agent.NOMBRE_DEL_AGENTE

Tu tarea es trabajar solo en tu fase.

Antes de modificar archivos, debes declarar:
- agente activo;
- fase;
- objetivo;
- archivos a leer;
- archivos a modificar;
- artefactos esperados;
- dependencias con otros agentes.

Debes respetar:
- docs/PROJECT_CONTEXT.md
- docs/AGENT_PROTOCOL.md
- docs/DECISIONS.md
- docs/API_CONTRACT.md
- docs/DATABASE_MODEL.md
- docs/UI_MAP.md
- docs/HANDOFFS.md

No puedes modificar archivos fuera de tu alcance sin dejar un handoff y pedir autorización.

Comienza revisando el contexto y proponiendo el primer avance.
```

---

## 4. Orden recomendado

1. Base de datos.
2. Backend.
3. Frontend.
4. QA.
5. Seguridad.
6. Documentación.
