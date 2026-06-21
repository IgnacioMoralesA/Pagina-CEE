"""Orquestador minimo de la fabrica SDD."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .agents import build_agent
from .constants import WORKFLOW_STEPS
from .harness import Harness
from .memory import remember_agent_result
from .schemas import WorkOrder, utc_now_iso
from .validators import validate_run


def init_project(project: str | Path) -> Path:
    return Harness(project).init_project()


def run_factory(project: str | Path, objective: str) -> dict[str, Any]:
    harness = Harness(project)
    run_id, run_path = harness.create_run(objective)
    work_order = WorkOrder(
        id="WO-" + hashlib.sha1(f"{run_id}|{objective}".encode("utf-8")).hexdigest()[:10],
        objective=objective,
        created_at=utc_now_iso(),
    )
    harness.write_work_order(run_path, work_order)
    work_order_payload = work_order.to_dict()

    for step in WORKFLOW_STEPS:
        phase = step["phase"]
        agent_id = step["agent_id"]
        if agent_id is None:
            harness.update_state(run_path, current_phase=phase)
            continue
        harness.update_state(run_path, current_phase=phase)
        agent = build_agent(agent_id, phase)
        result = agent.run(harness, run_path, work_order_payload)
        payload = harness.record_agent_result(run_path, result)
        harness.add_phase_result(run_path, payload)
        remember_agent_result(harness.project_path, payload, run_id)

    harness.update_state(run_path, status="complete", current_phase="complete")
    report = validate_run(run_path, write_report=True)
    return {
        "run_id": run_id,
        "run_path": str(run_path),
        "status": report.status,
        "validation_report": report.to_dict(),
    }


def latest_run(project: str | Path) -> Path | None:
    runs_dir = Path(project) / "runs"
    if not runs_dir.exists():
        return None
    runs = [path for path in runs_dir.iterdir() if path.is_dir() and path.name.startswith("RUN-")]
    if not runs:
        return None
    return max(runs, key=lambda path: path.stat().st_mtime)


def verify_project(project: str | Path) -> dict[str, Any]:
    run_path = latest_run(project)
    if run_path is None:
        return {
            "status": "error",
            "message": "No hay runs para verificar.",
            "run_path": None,
        }
    report = validate_run(run_path, write_report=True)
    return {
        "status": report.status,
        "message": "Verificacion completa" if report.status == "complete" else "Verificacion con errores",
        "run_path": str(run_path),
        "validation_report": report.to_dict(),
    }

