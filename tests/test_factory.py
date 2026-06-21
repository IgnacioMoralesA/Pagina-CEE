from __future__ import annotations

import json
from pathlib import Path

from factory.constants import REQUIRED_RUN_ARTIFACTS
from factory.orchestrator import init_project, run_factory, verify_project
from factory.registry import AGENT_DEFINITIONS


def test_agent_registry_contains_minimum_agents() -> None:
    expected = {
        "agent.product_owner",
        "agent.architect",
        "agent.database_designer",
        "agent.backend_developer",
        "agent.frontend_developer",
        "agent.qa_engineer",
        "agent.security_reviewer",
        "agent.documenter",
    }
    assert expected.issubset(AGENT_DEFINITIONS)


def test_project_initialization_creates_expected_directories(tmp_path: Path) -> None:
    project = tmp_path / "project"
    init_project(project)

    assert (project / "runs").is_dir()
    assert (project / "cache").is_dir()
    assert (project / "index").is_dir()
    assert (project / "agent-memory").is_dir()
    assert (project / "README.md").is_file()


def test_run_creates_required_artifacts_and_complete_final_report(tmp_path: Path) -> None:
    project = tmp_path / "project"
    result = run_factory(project, "Crear plataforma CEE Conecta")
    run_path = Path(result["run_path"])

    assert result["status"] == "complete"
    for artifact in REQUIRED_RUN_ARTIFACTS:
        assert (run_path / artifact).exists(), artifact

    final_report = json.loads((run_path / "final-report.json").read_text(encoding="utf-8"))
    assert final_report["status"] == "complete"


def test_verify_project_returns_complete(tmp_path: Path) -> None:
    project = tmp_path / "project"
    run_factory(project, "Crear plataforma CEE Conecta")

    result = verify_project(project)

    assert result["status"] == "complete"
    assert result["run_path"] is not None

