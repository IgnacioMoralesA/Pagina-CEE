"""Memoria local por proyecto y agente."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .observability import append_jsonl


def memory_file(project_path: Path, agent_id: str) -> Path:
    safe_name = agent_id.replace(".", "_")
    return project_path / "agent-memory" / f"{safe_name}.jsonl"


def remember_agent_result(project_path: Path, result: dict[str, Any], run_id: str) -> None:
    append_jsonl(
        memory_file(project_path, result["agent_id"]),
        {
            "event": "agent_result",
            "run_id": run_id,
            "phase": result["phase"],
            "status": result["status"],
            "artifacts": result["artifacts"],
        },
    )

