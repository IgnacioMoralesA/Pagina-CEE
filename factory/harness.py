"""Arnes local que media toda escritura y ejecucion de agentes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import PROJECT_DIRECTORIES, RUN_DIRECTORIES, WORKFLOW_STEPS
from .context import build_context_pack
from .observability import append_jsonl
from .registry import registry_as_dict
from .schemas import AgentResult, WorkOrder, utc_now_iso


class Harness:
    def __init__(self, project_path: str | Path) -> None:
        self.project_path = Path(project_path)

    def init_project(self) -> Path:
        self.project_path.mkdir(parents=True, exist_ok=True)
        for directory in PROJECT_DIRECTORIES:
            (self.project_path / directory).mkdir(parents=True, exist_ok=True)
        self._write_text_if_missing(
            self.project_path / "README.md",
            "# Proyecto CEE Conecta\n\nDirectorio de trabajo de la fabrica SDD.\n",
        )
        self._write_text_if_missing(
            self.project_path / "Aprendizaje.md",
            "# Aprendizaje\n\nRegistro incremental de decisiones y aprendizajes del proyecto.\n",
        )
        return self.project_path

    def create_run(self, objective: str) -> tuple[str, Path]:
        self.init_project()
        seed = f"{objective}|{utc_now_iso()}"
        run_id = "RUN-" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
        run_path = self.project_path / "runs" / run_id
        run_path.mkdir(parents=True, exist_ok=False)
        for directory in RUN_DIRECTORIES:
            (run_path / directory).mkdir(parents=True, exist_ok=True)

        self.write_json(run_path / "registries" / "agents.json", registry_as_dict())
        self.write_json(run_path / "routing" / "workflow.json", {"workflow": WORKFLOW_STEPS})
        self.write_json(run_path / "docs" / "context-pack.json", build_context_pack(objective))
        self.write_json(
            run_path / "state.json",
            {
                "run_id": run_id,
                "status": "running",
                "objective": objective,
                "current_phase": "intake",
                "phases": [],
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
        )
        self.log_tool(run_path, "create_run", {"run_id": run_id})
        return run_id, run_path

    def write_work_order(self, run_path: Path, work_order: WorkOrder) -> None:
        self.write_json(run_path / "work_order.json", work_order.to_dict())
        self.log_tool(run_path, "write_work_order", {"work_order_id": work_order.id})

    def write_artifact(self, run_path: Path, filename: str, content: str | dict[str, Any]) -> None:
        path = run_path / filename
        if isinstance(content, dict):
            self.write_json(path, content)
        else:
            self.write_text(path, content)
        self.log_tool(run_path, "write_artifact", {"artifact": filename})

    def record_agent_result(self, run_path: Path, result: AgentResult) -> dict[str, Any]:
        payload = result.to_dict()
        result_name = f"{result.agent_id}.{result.phase}.json".replace("/", "_")
        self.write_json(run_path / "agent-results" / result_name, payload)
        append_jsonl(
            run_path / "agent-logs" / f"{result.agent_id.replace('.', '_')}.jsonl",
            {
                "event": "agent_completed",
                "agent_id": result.agent_id,
                "phase": result.phase,
                "artifacts": result.artifacts,
            },
        )
        self.log_tool(run_path, "record_agent_result", {"agent_id": result.agent_id, "phase": result.phase})
        return payload

    def update_state(self, run_path: Path, **updates: Any) -> dict[str, Any]:
        state_path = run_path / "state.json"
        state = self.read_json(state_path)
        state.update(updates)
        state["updated_at"] = utc_now_iso()
        self.write_json(state_path, state)
        return state

    def add_phase_result(self, run_path: Path, phase_result: dict[str, Any]) -> None:
        state = self.read_json(run_path / "state.json")
        state.setdefault("phases", []).append(
            {
                "agent_id": phase_result["agent_id"],
                "phase": phase_result["phase"],
                "status": phase_result["status"],
                "artifacts": phase_result["artifacts"],
            }
        )
        state["current_phase"] = phase_result["phase"]
        state["updated_at"] = utc_now_iso()
        self.write_json(run_path / "state.json", state)

    def log_tool(self, run_path: Path, action: str, payload: dict[str, Any]) -> None:
        append_jsonl(run_path / "tool-logs" / "harness.jsonl", {"action": action, "payload": payload})

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_text_if_missing(path: Path, content: str) -> None:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

