"""CLI de la fabrica SDD."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .constants import DEFAULT_PROJECT_DIR
from .orchestrator import init_project, run_factory, verify_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m factory.cli", description="Fabrica SDD para CEE Conecta")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-project", help="Crea estructura local del proyecto de fabrica")
    init_parser.add_argument("--project", default=DEFAULT_PROJECT_DIR, help="Directorio del proyecto")

    run_parser = subparsers.add_parser("run", help="Ejecuta un run de fabrica")
    run_parser.add_argument("--project", default=DEFAULT_PROJECT_DIR, help="Directorio del proyecto")
    run_parser.add_argument("--objective", required=True, help="Objetivo del work order")

    verify_parser = subparsers.add_parser("verify", help="Verifica el ultimo run")
    verify_parser.add_argument("--project", default=DEFAULT_PROJECT_DIR, help="Directorio del proyecto")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init-project":
        project_path = init_project(args.project)
        print(json.dumps({"status": "complete", "project": str(Path(project_path))}, indent=2))
        return 0

    if args.command == "run":
        result = run_factory(args.project, args.objective)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "complete" else 1

    if args.command == "verify":
        result = verify_project(args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "complete" else 1

    parser.error(f"Comando no soportado: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())

