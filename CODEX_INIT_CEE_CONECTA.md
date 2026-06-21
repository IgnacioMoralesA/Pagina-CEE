# CODEX_INIT.md

# CEE Conecta — Inicio del proyecto con fábrica agéntica SDD

## 1. Propósito de este archivo

Este archivo debe ser usado como instrucción inicial para Codex al comenzar el desarrollo del proyecto.

El objetivo no es pedirle a Codex que implemente todo el sistema de una vez, sino que inicialice una estructura de trabajo controlada mediante una fábrica agéntica inspirada en un arnés SDD local, determinístico, auditable y trazable.

El producto final será una aplicación web para un Centro de Estudiantes.

La fábrica agéntica será el proceso usado para construir el producto, no necesariamente una funcionalidad interna visible para los usuarios finales.

---

# 2. Producto a construir

## Nombre del producto

CEE Conecta

## Descripción breve

CEE Conecta es una plataforma web para centralizar la gestión de un Centro de Estudiantes universitario. El sistema permitirá administrar información pública, noticias, eventos, solicitudes estudiantiles, documentos, actas, finanzas básicas, inventario, votaciones, usuarios y transparencia.

## Objetivo del producto

Construir una aplicación web funcional que permita al Centro de Estudiantes organizar su trabajo, mejorar la comunicación con los estudiantes, mantener trazabilidad de sus procesos y conservar memoria institucional entre directivas.

---

# 3. Interpretación correcta del proyecto del curso

La fábrica agéntica no debe entenderse como una característica obligatoria dentro del producto final.

La fábrica agéntica debe utilizarse como método de desarrollo del software.

Por lo tanto, el proyecto debe demostrar dos cosas:

1. Producto final:
   - Aplicación web CEE Conecta.

2. Proceso de construcción:
   - Fábrica agéntica SDD con agentes, workflows, arnés, evidencia, validación y cierre técnico.

---

# 4. Referencia de fábrica

La fábrica debe inspirarse en una arquitectura similar a ARNES SDD:

- work orders estrictos;
- agentes especializados;
- ejecución mediante arnés;
- registro de agentes, skills y herramientas;
- context-pack;
- evidence-register;
- memoria por proyecto/agente;
- gates de validación;
- reportes de cierre;
- trazabilidad;
- ejecución reproducible;
- logs en JSONL;
- validadores de schema, policy, safety, cobertura y formato final.

No se requiere implementar agentes autónomos reales con llamadas externas en la primera etapa.

La primera versión puede ser determinística y local, usando funciones que representen agentes especializados y generen artefactos estructurados.

---

# 5. Regla principal de trabajo para Codex

No implementar todo el producto de una vez.

Primero se debe construir la base del proyecto y la fábrica mínima.

Orden obligatorio inicial:

1. Crear estructura de carpetas.
2. Crear documentos base de la fábrica.
3. Crear contratos de work order, agentes y resultados.
4. Crear orquestador mínimo.
5. Crear arnés mínimo.
6. Crear agentes determinísticos iniciales.
7. Crear primer run de ejemplo.
8. Generar especificación inicial del producto.
9. Recién después comenzar backend/frontend.

---

# 6. Estructura inicial esperada

Crear la siguiente estructura base:

```text
cee-conecta/
|-- README.md
|-- CODEX_INIT.md
|-- pyproject.toml
|-- .gitignore
|
|-- factory/
|   |-- __init__.py
|   |-- constants.py
|   |-- schemas.py
|   |-- registry.py
|   |-- orchestrator.py
|   |-- harness.py
|   |-- agents.py
|   |-- validators.py
|   |-- context.py
|   |-- memory.py
|   |-- observability.py
|   |-- cli.py
|
|-- docs/
|   |-- 01_vision_producto.md
|   |-- 02_especificacion_resumida.md
|   |-- 03_arquitectura.md
|   |-- 04_agentes_workflows.md
|   |-- 05_checklist_validacion.md
|
|-- project/
|   |-- README.md
|   |-- Aprendizaje.md
|   |-- runs/
|   |-- cache/
|   |-- index/
|   |-- agent-memory/
|
|-- app/
|   |-- backend/
|   |-- frontend/
|   |-- database/
|   |-- docs/
|
|-- tests/
|   |-- test_factory.py
```

---

# 7. Stack recomendado para el producto

Para facilitar el desarrollo, usar el siguiente stack salvo que el usuario indique lo contrario:

## Backend

FastAPI con Python.

## Frontend

React con Vite.

## Base de datos

PostgreSQL.

## Autenticación

Google OAuth / OpenID Connect para correo institucional.

## Pruebas

Pytest para backend y factory.
Vitest o Playwright para frontend cuando corresponda.

---

# 8. Alcance funcional del producto CEE Conecta

El producto final debe considerar al menos los siguientes módulos:

## 8.1 Usuarios y autenticación

- login con Google institucional;
- registro automático de usuario;
- roles;
- permisos;
- estado de usuario;
- auditoría de accesos.

Roles sugeridos:

```text
STUDENT
BOARD_MEMBER
PRESIDENT
TREASURER
SECRETARY
ADMIN
```

## 8.2 Página pública

- inicio;
- noticias;
- comunicados;
- eventos;
- directiva;
- documentos públicos;
- transparencia;
- contacto.

## 8.3 Noticias y comunicados

- crear publicación;
- editar publicación;
- publicar;
- archivar;
- adjuntar imagen;
- categorizar;
- controlar estado.

## 8.4 Eventos

- crear evento;
- publicar evento;
- definir fecha, lugar, cupos;
- inscripción de estudiantes;
- control de asistencia;
- cancelación de evento;
- reporte de participantes.

## 8.5 Solicitudes estudiantiles

- crear solicitud;
- clasificar solicitud;
- adjuntar documentos;
- revisar estado;
- responder solicitud;
- cerrar solicitud.

Estados sugeridos:

```text
SUBMITTED
IN_REVIEW
OBSERVED
APPROVED
REJECTED
CLOSED
```

## 8.6 Reuniones, actas y acuerdos

- crear reunión;
- registrar participantes;
- subir acta;
- registrar acuerdos;
- asignar responsables;
- seguimiento de acuerdos.

## 8.7 Finanzas y transparencia

- presupuesto;
- ingresos;
- egresos;
- categorías;
- comprobantes;
- rendiciones;
- resumen financiero;
- publicación de transparencia.

## 8.8 Inventario

- recursos del CEE;
- categorías;
- préstamos;
- devoluciones;
- historial de movimientos;
- estado físico del recurso.

## 8.9 Documentos

- subir documentos;
- clasificar documentos;
- definir visibilidad pública/privada;
- versionar documentos;
- descargar documentos.

## 8.10 Encuestas y votaciones

- crear encuesta;
- responder encuesta;
- crear votación;
- votar una vez por usuario;
- cerrar votación;
- ver resultados.

---

# 9. Fábrica agéntica de desarrollo

La fábrica debe tener agentes que produzcan artefactos del desarrollo.

## 9.1 Agentes mínimos

### agent.product_owner

Responsabilidad:

- transformar la idea inicial en objetivos, alcance, actores y requisitos.

Artefactos:

- `spec.md`
- `use-cases.md`
- `business-rules.md`

### agent.architect

Responsabilidad:

- definir arquitectura, stack, módulos y estructura del sistema.

Artefactos:

- `architecture.md`
- `module-map.md`

### agent.database_designer

Responsabilidad:

- diseñar tablas, relaciones, claves y restricciones.

Artefactos:

- `database-model.md`
- `schema.sql`

### agent.backend_developer

Responsabilidad:

- definir API REST, endpoints, servicios y validaciones backend.

Artefactos:

- `api-contract.md`
- `openapi.yaml`

### agent.frontend_developer

Responsabilidad:

- definir pantallas, componentes y flujos frontend.

Artefactos:

- `ui-map.md`
- `screens.md`

### agent.qa_engineer

Responsabilidad:

- generar plan de pruebas, checklist y cobertura esperada.

Artefactos:

- `test-plan.md`
- `coverage-plan.md`
- `validation-report.json`

### agent.security_reviewer

Responsabilidad:

- revisar autenticación, permisos, datos sensibles y archivos.

Artefactos:

- `security-review.md`

### agent.documenter

Responsabilidad:

- generar documentación técnica, reporte final y cierre.

Artefactos:

- `final-report.json`
- `RUN_STATE.md`
- `CHECKLIST_APLICADO.md`

---

# 10. Workflow SDD inicial

Implementar inicialmente el siguiente flujo:

```text
intake
↓
specify
↓
architecture
↓
database
↓
api_design
↓
ui_design
↓
implementation_plan
↓
qa_plan
↓
security_review
↓
close
```

Cada fase debe crear evidencia y artefactos dentro de:

```text
project/runs/RUN-<hash>/
```

---

# 11. Artefactos mínimos por run

Cada ejecución de la fábrica debe generar:

```text
work_order.json
state.json
spec.md
use-cases.md
business-rules.md
architecture.md
database-model.md
schema.sql
api-contract.md
openapi.yaml
ui-map.md
screens.md
implementation-plan.md
test-plan.md
coverage-plan.md
security-review.md
traceability-matrix.md
validation-report.json
final-report.json
RUN_STATE.md
CHECKLIST_APLICADO.md
```

Directorios:

```text
agent-results/
agent-logs/
tool-logs/
registries/
routing/
docs/
```

---

# 12. Work order inicial del proyecto

La fábrica debe aceptar un objetivo como este:

```text
Crear una plataforma web para la gestión de un Centro de Estudiantes universitario, con login institucional mediante Google, noticias, eventos, solicitudes estudiantiles, documentos, finanzas, inventario, reuniones, actas, votaciones y transparencia.
```

El `work_order.json` debe incluir:

- id;
- objetivo;
- tipo de trabajo;
- alcance;
- exclusiones;
- restricciones;
- salidas esperadas;
- aprobaciones requeridas.

---

# 13. Restricciones de seguridad de la fábrica

La fábrica no debe:

- leer secretos;
- desplegar a producción;
- modificar servicios externos sin aprobación;
- escribir en bases de datos reales sin autorización;
- ejecutar comandos destructivos;
- mezclar artefactos generados con evidencia sin registrar.

Toda acción debe pasar por el arnés.

---

# 14. Validadores mínimos

Implementar validadores para:

1. Schema.
2. Evidencia.
3. Policy.
4. Safety.
5. Consistencia.
6. Cobertura.
7. Formato final.

Estados finales permitidos:

```text
complete
needs_user_input
not_answerable
error
```

---

# 15. Evidencia mínima

Cada agente debe devolver un resultado con:

```json
{
  "agent_id": "...",
  "phase": "...",
  "status": "complete",
  "artifacts": [],
  "evidence_refs": [],
  "critical_claims": [],
  "policy_findings": [],
  "coverage": {}
}
```

---

# 16. Qué hacer primero

Codex debe comenzar por implementar una fábrica mínima ejecutable.

Primera tarea concreta:

## Tarea 1

Crear la estructura de carpetas y archivos base.

## Tarea 2

Implementar:

- `factory/constants.py`
- `factory/schemas.py`
- `factory/registry.py`

## Tarea 3

Implementar:

- `factory/agents.py`
- `factory/harness.py`
- `factory/orchestrator.py`

con agentes determinísticos que escriban archivos Markdown/JSON.

## Tarea 4

Implementar CLI:

```bash
python -m factory.cli init-project --project project
python -m factory.cli run --project project --objective "Crear CEE Conecta"
python -m factory.cli verify --project project
```

## Tarea 5

Crear tests mínimos:

```bash
pytest -q tests
```

Los tests deben validar:

- registros de agentes;
- creación de proyecto;
- ejecución de run;
- existencia de artefactos mínimos;
- `final-report.json.status = complete`.

---

# 17. Criterio de avance

No avanzar al backend/frontend hasta que exista:

- fábrica mínima;
- run exitoso;
- artefactos generados;
- verificación CLI;
- tests de fábrica pasando.

---

# 18. Entrega esperada después del primer avance

Después de la primera implementación, el proyecto debe poder ejecutar:

```bash
python -m factory.cli init-project --project project
python -m factory.cli run --project project --objective "Crear plataforma CEE Conecta"
python -m factory.cli verify --project project
pytest -q tests
```

Y debe terminar con:

```text
final-report.json.status = complete
```

---

# 19. Nota de diseño

La aplicación CEE Conecta puede ser una aplicación web tradicional.

No es obligatorio que CEE Conecta use agentes internamente.

La evidencia de la evaluación estará en el proceso de construcción mediante la fábrica agéntica, no en que el producto final tenga inteligencia artificial embebida.

---

# 20. Próximo paso después de la fábrica mínima

Cuando la fábrica mínima funcione, usar sus artefactos para implementar el producto en este orden:

1. Backend base.
2. Modelo de datos.
3. Autenticación Google.
4. Roles y permisos.
5. Noticias.
6. Eventos.
7. Solicitudes.
8. Documentos.
9. Finanzas.
10. Inventario.
11. Reuniones y actas.
12. Encuestas y votaciones.
13. Frontend.
14. Pruebas.
15. Documentación.
16. Cierre técnico.
