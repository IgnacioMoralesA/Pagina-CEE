"""Agentes deterministas iniciales de la fabrica."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .constants import PRODUCT_MODULES, PRODUCT_NAME
from .harness import Harness
from .schemas import AgentResult

ArtifactMap = dict[str, str | dict[str, Any]]
Renderer = Callable[[dict[str, Any], dict[str, Any]], ArtifactMap]


class DeterministicAgent:
    def __init__(self, agent_id: str, phase: str, renderer: Renderer) -> None:
        self.agent_id = agent_id
        self.phase = phase
        self.renderer = renderer

    def run(self, harness: Harness, run_path: Path, work_order: dict[str, Any]) -> AgentResult:
        artifacts = self.renderer(work_order, {"run_path": str(run_path)})
        for filename, content in artifacts.items():
            harness.write_artifact(run_path, filename, content)
        artifact_names = list(artifacts.keys())
        return AgentResult(
            agent_id=self.agent_id,
            phase=self.phase,
            artifacts=artifact_names,
            evidence_refs=artifact_names,
            critical_claims=[
                f"{self.agent_id} genero artefactos deterministas para {self.phase}.",
            ],
            policy_findings=[],
            coverage={"artifacts_created": len(artifact_names), "modules_considered": list(PRODUCT_MODULES)},
        )


def build_agent(agent_id: str, phase: str) -> DeterministicAgent:
    key = (agent_id, phase)
    try:
        renderer = RENDERERS[key]
    except KeyError as exc:
        raise KeyError(f"No existe agente deterministico para {agent_id} en fase {phase}") from exc
    return DeterministicAgent(agent_id=agent_id, phase=phase, renderer=renderer)


def render_product_owner(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    objective = work_order["objective"]
    modules = "\n".join(f"- {module.replace('_', ' ')}" for module in PRODUCT_MODULES)
    return {
        "spec.md": f"""# Especificacion inicial - {PRODUCT_NAME}

## Objetivo

{objective}

## Alcance inicial

La plataforma centralizara la gestion de un Centro de Estudiantes universitario
con foco en trazabilidad, comunicacion publica y memoria institucional.

## Modulos considerados

{modules}

## Limite de esta ejecucion

Esta ejecucion genera artefactos de fabrica. No implementa backend ni frontend.
""",
        "use-cases.md": """# Casos de uso iniciales

- Estudiante revisa noticias, eventos y documentos publicos.
- Estudiante crea y consulta una solicitud estudiantil.
- Directiva publica comunicados, documentos y transparencia.
- Tesoreria registra ingresos, egresos y comprobantes.
- Secretaria registra reuniones, actas y acuerdos.
- Administracion gestiona roles, permisos y estados de usuarios.
""",
        "business-rules.md": """# Reglas de negocio iniciales

- El acceso privado requiere identidad institucional validada.
- Un usuario debe tener exactamente un estado operativo activo o bloqueado.
- Las votaciones deben permitir un voto por usuario habilitado.
- Los documentos pueden ser publicos o privados segun su clasificacion.
- Todo cambio sensible debe dejar evidencia auditable.
- Los comprobantes financieros deben mantener trazabilidad con su movimiento.
""",
    }


def render_architecture(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "architecture.md": """# Arquitectura propuesta

## Stack objetivo

- Backend: FastAPI.
- Frontend: React con Vite.
- Base de datos: PostgreSQL.
- Autenticacion: Google OAuth / OpenID Connect institucional.
- Pruebas: Pytest, Vitest y Playwright cuando corresponda.

## Estilo de arquitectura

Aplicacion web modular con API REST, capa de servicios, persistencia relacional
y frontend orientado a flujos administrativos y publicos.

## Restriccion activa

Este run solo produce diseno y evidencia. La implementacion del producto queda
para etapas posteriores.
""",
        "module-map.md": """# Mapa de modulos

- Identity: usuarios, roles, permisos y auditoria de acceso.
- Public Site: inicio, noticias, comunicados, directiva y contacto.
- Events: eventos, inscripciones, cupos y asistencia.
- Requests: solicitudes estudiantiles y ciclo de respuesta.
- Meetings: reuniones, actas, acuerdos y responsables.
- Finance: presupuesto, ingresos, egresos y transparencia.
- Inventory: recursos, prestamos, devoluciones e historial.
- Documents: carga, clasificacion, visibilidad y versiones.
- Polls: encuestas, votaciones y resultados.
""",
    }


def render_database(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "database-model.md": """# Modelo de datos inicial

## Entidades principales

- users, roles, user_roles, audit_events.
- posts, events, event_registrations.
- student_requests, request_attachments, request_comments.
- meetings, meeting_participants, minutes, agreements.
- finance_categories, financial_movements, receipts.
- inventory_items, inventory_loans.
- documents, document_versions.
- surveys, survey_questions, survey_responses.
- votes, vote_options, vote_ballots.

## Criterios

- Usar claves primarias UUID.
- Registrar timestamps de creacion y actualizacion.
- Mantener claves foraneas explicitas.
- Separar datos publicos y privados por permisos de aplicacion.
""",
        "schema.sql": """-- Borrador de esquema para CEE Conecta.
-- No ejecutar contra bases reales en esta etapa.

CREATE TABLE users (
  id UUID PRIMARY KEY,
  institutional_email TEXT NOT NULL UNIQUE,
  full_name TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE roles (
  id UUID PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL
);

CREATE TABLE student_requests (
  id UUID PRIMARY KEY,
  requester_id UUID NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL
);
""",
    }


def render_api_design(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "api-contract.md": """# Contrato API inicial

## Convenciones

- Prefijo base: `/api/v1`.
- Autenticacion privada mediante token de sesion derivado de Google OIDC.
- Errores con `code`, `message` y `details`.
- Operaciones sensibles deben registrar auditoria.

## Recursos iniciales

- `/auth/session`
- `/users`
- `/posts`
- `/events`
- `/requests`
- `/documents`
- `/finance/movements`
- `/inventory/items`
- `/meetings`
- `/polls`
""",
        "openapi.yaml": """openapi: 3.1.0
info:
  title: CEE Conecta API
  version: 0.1.0
paths:
  /api/v1/health:
    get:
      summary: Healthcheck de aplicacion
      responses:
        "200":
          description: Servicio disponible
  /api/v1/requests:
    get:
      summary: Lista solicitudes estudiantiles visibles para el usuario
      responses:
        "200":
          description: Solicitudes encontradas
    post:
      summary: Crea una solicitud estudiantil
      responses:
        "201":
          description: Solicitud creada
""",
    }


def render_ui_design(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "ui-map.md": """# Mapa UI inicial

- Publico: inicio, noticias, eventos, documentos publicos, transparencia.
- Estudiante: panel personal, solicitudes, inscripciones, votaciones.
- Directiva: tablero operativo, publicaciones, eventos, documentos.
- Tesoreria: movimientos, comprobantes, resumen financiero.
- Secretaria: reuniones, actas, acuerdos y seguimiento.
- Administracion: usuarios, roles, permisos y auditoria.
""",
        "screens.md": """# Pantallas iniciales

## Publico

- Home del CEE.
- Lista y detalle de noticias.
- Calendario/lista de eventos.
- Transparencia y documentos publicos.

## Privado

- Dashboard por rol.
- Bandeja de solicitudes.
- Editor de publicaciones.
- Registro financiero.
- Inventario y prestamos.
- Reuniones y acuerdos.
""",
    }


def render_implementation_plan(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "implementation-plan.md": """# Plan de implementacion incremental

1. Consolidar fabrica minima y validadores.
2. Implementar backend base con FastAPI.
3. Crear modelo de datos y migraciones.
4. Integrar autenticacion Google OIDC.
5. Implementar roles y permisos.
6. Construir modulos funcionales priorizados.
7. Implementar frontend React con flujos principales.
8. Agregar pruebas, documentacion y cierre tecnico.

## Criterio de avance actual

No comenzar backend ni frontend hasta que la fabrica verifique un run completo.
""",
    }


def render_qa_plan(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "test-plan.md": """# Plan de pruebas inicial

## Fabrica

- Registro de agentes.
- Inicializacion de proyecto.
- Ejecucion de run.
- Existencia de artefactos obligatorios.
- Estado final completo.

## Producto futuro

- Pruebas unitarias backend.
- Pruebas de contratos API.
- Pruebas de permisos por rol.
- Pruebas de interfaz y flujos criticos.
""",
        "coverage-plan.md": """# Plan de cobertura

- La fabrica debe cubrir contratos, orquestacion y validacion.
- El backend futuro debe cubrir servicios, permisos y validaciones.
- El frontend futuro debe cubrir render, navegacion y formularios criticos.
- Los modulos sensibles deben incluir casos negativos y auditoria.
""",
    }


def render_security_review(work_order: dict[str, Any], _: dict[str, Any]) -> ArtifactMap:
    return {
        "security-review.md": """# Revision de seguridad inicial

## Hallazgos

- No se usan secretos en esta etapa.
- No se ejecutan integraciones externas.
- No se escribe en bases de datos reales.
- Backend y frontend quedan sin implementar por restriccion de alcance.

## Requisitos futuros

- Validar dominio institucional en Google OIDC.
- Aplicar RBAC por rol y permiso.
- Auditar operaciones sensibles.
- Proteger documentos privados y comprobantes.
- Validar archivos adjuntos por tipo, tamano y visibilidad.
""",
    }


def render_close(work_order: dict[str, Any], context: dict[str, Any]) -> ArtifactMap:
    objective = work_order["objective"]
    return {
        "traceability-matrix.md": """# Matriz de trazabilidad inicial

| Necesidad | Artefacto | Estado |
| --- | --- | --- |
| Objetivo y alcance | spec.md | cubierto |
| Casos de uso | use-cases.md | cubierto |
| Reglas de negocio | business-rules.md | cubierto |
| Arquitectura | architecture.md | cubierto |
| Datos | database-model.md, schema.sql | cubierto |
| API | api-contract.md, openapi.yaml | cubierto |
| UI | ui-map.md, screens.md | cubierto |
| QA | test-plan.md, coverage-plan.md | cubierto |
| Seguridad | security-review.md | cubierto |
""",
        "final-report.json": {
            "status": "complete",
            "product": PRODUCT_NAME,
            "objective": objective,
            "summary": "Fabrica minima ejecutada con agentes deterministas y artefactos obligatorios.",
            "backend_implemented": False,
            "frontend_implemented": False,
            "validation_report": "validation-report.json",
        },
        "RUN_STATE.md": """# Estado del run

Estado: complete

La fabrica genero los artefactos iniciales requeridos y mantiene la restriccion
de no implementar backend ni frontend en esta etapa.
""",
        "CHECKLIST_APLICADO.md": """# Checklist aplicado

- [x] Work order creado.
- [x] Agentes deterministas ejecutados.
- [x] Artefactos minimos generados.
- [x] Evidencia y logs registrados.
- [x] Validadores listos para verificacion.
- [x] Backend no implementado.
- [x] Frontend no implementado.
""",
    }


RENDERERS: dict[tuple[str, str], Renderer] = {
    ("agent.product_owner", "specify"): render_product_owner,
    ("agent.architect", "architecture"): render_architecture,
    ("agent.database_designer", "database"): render_database,
    ("agent.backend_developer", "api_design"): render_api_design,
    ("agent.frontend_developer", "ui_design"): render_ui_design,
    ("agent.architect", "implementation_plan"): render_implementation_plan,
    ("agent.qa_engineer", "qa_plan"): render_qa_plan,
    ("agent.security_reviewer", "security_review"): render_security_review,
    ("agent.documenter", "close"): render_close,
}

