"""Validadores minimos de schema, evidencia, policy, safety y cierre."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import (
    ALLOWED_FINAL_STATUSES,
    FORBIDDEN_ACTIONS,
    REQUIRED_RUN_ARTIFACTS,
    WORKFLOW_STEPS,
)
from .harness import Harness
from .schemas import (
    ValidationFinding,
    ValidationReport,
    required_agent_result_keys,
    required_work_order_keys,
)


def validate_run(run_path: str | Path, write_report: bool = True) -> ValidationReport:
    path = Path(run_path)
    findings = [
        validate_schema(path),
        validate_evidence(path),
        validate_policy(path),
        validate_safety(path),
        validate_consistency(path),
        validate_coverage(path),
        validate_final_format(path),
    ]
    status = "complete" if all(finding.status == "complete" for finding in findings) else "error"
    report = ValidationReport(status=status, findings=findings)
    if write_report:
        Harness.write_json(path / "validation-report.json", report.to_dict())
    return report


def validate_schema(run_path: Path) -> ValidationFinding:
    issues: list[str] = []
    work_order_path = run_path / "work_order.json"
    if not work_order_path.exists():
        issues.append("work_order.json no existe")
    else:
        work_order = _read_json(work_order_path)
        missing = sorted(required_work_order_keys() - set(work_order))
        if missing:
            issues.append(f"work_order.json sin llaves: {missing}")

    result_files = list((run_path / "agent-results").glob("*.json"))
    if not result_files:
        issues.append("No hay resultados de agentes")
    for result_file in result_files:
        payload = _read_json(result_file)
        missing = sorted(required_agent_result_keys() - set(payload))
        if missing:
            issues.append(f"{result_file.name} sin llaves: {missing}")

    return _finding("schema", issues, {"agent_results": len(result_files)})


def validate_evidence(run_path: Path) -> ValidationFinding:
    issues: list[str] = []
    for result_file in (run_path / "agent-results").glob("*.json"):
        payload = _read_json(result_file)
        for artifact in payload.get("artifacts", []):
            if not (run_path / artifact).exists():
                issues.append(f"Artefacto declarado no existe: {artifact}")
        for evidence in payload.get("evidence_refs", []):
            if not (run_path / evidence).exists():
                issues.append(f"Evidencia declarada no existe: {evidence}")
    return _finding("evidence", issues)


def validate_policy(run_path: Path) -> ValidationFinding:
    issues: list[str] = []
    work_order = _read_json(run_path / "work_order.json") if (run_path / "work_order.json").exists() else {}
    constraints = " ".join(work_order.get("constraints", [])).lower()
    if "no leer secretos" not in constraints:
        issues.append("El work order no declara restriccion de secretos")
    final_report_path = run_path / "final-report.json"
    if final_report_path.exists():
        final_report = _read_json(final_report_path)
        if final_report.get("backend_implemented") is not False:
            issues.append("El reporte final debe declarar backend_implemented=false")
        if final_report.get("frontend_implemented") is not False:
            issues.append("El reporte final debe declarar frontend_implemented=false")
    return _finding("policy", issues, {"forbidden_actions": FORBIDDEN_ACTIONS})


def validate_safety(run_path: Path) -> ValidationFinding:
    issues: list[str] = []
    tool_log = run_path / "tool-logs" / "harness.jsonl"
    if not tool_log.exists():
        issues.append("No existe log del arnes")
    searchable_files = list(run_path.glob("*.md")) + list(run_path.glob("*.json")) + list(run_path.glob("*.sql"))
    joined = "\n".join(path.read_text(encoding="utf-8", errors="ignore").lower() for path in searchable_files)
    destructive_tokens = ["rm -rf", "git reset --hard", "drop database", "deploy production"]
    for token in destructive_tokens:
        if token in joined:
            issues.append(f"Token destructivo detectado: {token}")
    return _finding("safety", issues)


def validate_consistency(run_path: Path) -> ValidationFinding:
    issues: list[str] = []
    state_path = run_path / "state.json"
    if not state_path.exists():
        return _finding("consistency", ["state.json no existe"])
    state = _read_json(state_path)
    expected_phases = [step["phase"] for step in WORKFLOW_STEPS if step["agent_id"]]
    actual_phases = [phase.get("phase") for phase in state.get("phases", [])]
    missing = [phase for phase in expected_phases if phase not in actual_phases]
    if missing:
        issues.append(f"Faltan fases en state.json: {missing}")
    if state.get("status") != "complete":
        issues.append("state.json no esta en estado complete")
    return _finding("consistency", issues, {"actual_phases": actual_phases})


def validate_coverage(run_path: Path) -> ValidationFinding:
    existing = {path.name for path in run_path.iterdir() if path.is_file()}
    existing.add("validation-report.json")
    missing = [artifact for artifact in REQUIRED_RUN_ARTIFACTS if artifact not in existing]
    return _finding("coverage", [f"Faltan artefactos: {missing}"] if missing else [], {"required": REQUIRED_RUN_ARTIFACTS})


def validate_final_format(run_path: Path) -> ValidationFinding:
    issues: list[str] = []
    final_report_path = run_path / "final-report.json"
    if not final_report_path.exists():
        return _finding("final_format", ["final-report.json no existe"])
    final_report = _read_json(final_report_path)
    status = final_report.get("status")
    if status not in ALLOWED_FINAL_STATUSES:
        issues.append(f"Estado final invalido: {status}")
    if status != "complete":
        issues.append("El estado final esperado para esta etapa es complete")
    return _finding("final_format", issues, {"status": status})


def _finding(validator: str, issues: list[str], details: dict[str, Any] | None = None) -> ValidationFinding:
    return ValidationFinding(
        validator=validator,
        status="complete" if not issues else "error",
        message="ok" if not issues else "; ".join(issues),
        details=details or {},
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

