"""Registro local de agentes y sus responsabilidades."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class AgentDefinition:
    agent_id: str
    role: str
    phases: tuple[str, ...]
    artifacts: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


AGENT_DEFINITIONS: dict[str, AgentDefinition] = {
    "agent.product_owner": AgentDefinition(
        agent_id="agent.product_owner",
        role="Product Owner",
        phases=("specify",),
        artifacts=("spec.md", "use-cases.md", "business-rules.md"),
        description="Transforma la idea inicial en objetivos, alcance, actores y requisitos.",
    ),
    "agent.architect": AgentDefinition(
        agent_id="agent.architect",
        role="Software Architect",
        phases=("architecture", "implementation_plan"),
        artifacts=("architecture.md", "module-map.md", "implementation-plan.md"),
        description="Define arquitectura, stack, modulos y plan incremental.",
    ),
    "agent.database_designer": AgentDefinition(
        agent_id="agent.database_designer",
        role="Database Designer",
        phases=("database",),
        artifacts=("database-model.md", "schema.sql"),
        description="Disena tablas, relaciones, claves y restricciones.",
    ),
    "agent.backend_developer": AgentDefinition(
        agent_id="agent.backend_developer",
        role="Backend Developer",
        phases=("api_design",),
        artifacts=("api-contract.md", "openapi.yaml"),
        description="Define contrato REST, servicios y validaciones backend sin implementar codigo.",
    ),
    "agent.frontend_developer": AgentDefinition(
        agent_id="agent.frontend_developer",
        role="Frontend Developer",
        phases=("ui_design",),
        artifacts=("ui-map.md", "screens.md"),
        description="Define pantallas, componentes y flujos frontend sin implementar codigo.",
    ),
    "agent.qa_engineer": AgentDefinition(
        agent_id="agent.qa_engineer",
        role="QA Engineer",
        phases=("qa_plan",),
        artifacts=("test-plan.md", "coverage-plan.md"),
        description="Genera plan de pruebas, checklist y cobertura esperada.",
    ),
    "agent.security_reviewer": AgentDefinition(
        agent_id="agent.security_reviewer",
        role="Security Reviewer",
        phases=("security_review",),
        artifacts=("security-review.md",),
        description="Revisa autenticacion, permisos, datos sensibles y archivos.",
    ),
    "agent.documenter": AgentDefinition(
        agent_id="agent.documenter",
        role="Technical Documenter",
        phases=("close",),
        artifacts=(
            "traceability-matrix.md",
            "final-report.json",
            "RUN_STATE.md",
            "CHECKLIST_APLICADO.md",
        ),
        description="Genera documentacion tecnica, reporte final y cierre.",
    ),
}


def get_agent(agent_id: str) -> AgentDefinition:
    try:
        return AGENT_DEFINITIONS[agent_id]
    except KeyError as exc:
        raise KeyError(f"Agente no registrado: {agent_id}") from exc


def list_agents() -> list[AgentDefinition]:
    return list(AGENT_DEFINITIONS.values())


def registry_as_dict(agents: Iterable[AgentDefinition] | None = None) -> dict[str, object]:
    selected = list(agents or list_agents())
    return {
        "version": 1,
        "agents": [agent.to_dict() for agent in selected],
    }

