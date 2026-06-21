"""Contratos serializables de work orders, agentes y validacion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .constants import PRODUCT_MODULES, REQUIRED_RUN_ARTIFACTS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class WorkOrder:
    id: str
    objective: str
    work_type: str = "software_factory_run"
    scope: list[str] = field(default_factory=lambda: list(PRODUCT_MODULES))
    exclusions: list[str] = field(
        default_factory=lambda: [
            "No implementar backend en esta etapa.",
            "No implementar frontend en esta etapa.",
            "No integrar servicios externos.",
        ]
    )
    constraints: list[str] = field(
        default_factory=lambda: [
            "Ejecucion local y deterministica.",
            "No leer secretos.",
            "No desplegar a produccion.",
            "Toda accion debe pasar por el arnes.",
        ]
    )
    expected_outputs: list[str] = field(default_factory=lambda: list(REQUIRED_RUN_ARTIFACTS))
    required_approvals: list[str] = field(
        default_factory=lambda: [
            "Aprobacion del usuario antes de implementar backend.",
            "Aprobacion del usuario antes de implementar frontend.",
            "Aprobacion del usuario antes de usar servicios externos.",
        ]
    )
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    agent_id: str
    phase: str
    status: str = "complete"
    artifacts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    critical_claims: list[str] = field(default_factory=list)
    policy_findings: list[str] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now_iso)
    completed_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationFinding:
    validator: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    status: str
    findings: list[ValidationFinding]
    generated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def required_agent_result_keys() -> set[str]:
    return {
        "agent_id",
        "phase",
        "status",
        "artifacts",
        "evidence_refs",
        "critical_claims",
        "policy_findings",
        "coverage",
    }


def required_work_order_keys() -> set[str]:
    return {
        "id",
        "objective",
        "work_type",
        "scope",
        "exclusions",
        "constraints",
        "expected_outputs",
        "required_approvals",
    }

