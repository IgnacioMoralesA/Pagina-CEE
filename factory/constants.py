"""Constantes compartidas de la fabrica SDD."""

PRODUCT_NAME = "CEE Conecta"
DEFAULT_PROJECT_DIR = "project"

ALLOWED_FINAL_STATUSES = {
    "complete",
    "needs_user_input",
    "not_answerable",
    "error",
}

RUN_DIRECTORIES = [
    "agent-results",
    "agent-logs",
    "tool-logs",
    "registries",
    "routing",
    "docs",
]

PROJECT_DIRECTORIES = [
    "runs",
    "cache",
    "index",
    "agent-memory",
]

APP_DIRECTORIES = [
    "app/backend",
    "app/frontend",
    "app/database",
    "app/docs",
]

REQUIRED_RUN_ARTIFACTS = [
    "work_order.json",
    "state.json",
    "spec.md",
    "use-cases.md",
    "business-rules.md",
    "architecture.md",
    "database-model.md",
    "schema.sql",
    "api-contract.md",
    "openapi.yaml",
    "ui-map.md",
    "screens.md",
    "implementation-plan.md",
    "test-plan.md",
    "coverage-plan.md",
    "security-review.md",
    "traceability-matrix.md",
    "validation-report.json",
    "final-report.json",
    "RUN_STATE.md",
    "CHECKLIST_APLICADO.md",
]

PRODUCT_MODULES = [
    "usuarios_y_autenticacion",
    "pagina_publica",
    "noticias_y_comunicados",
    "eventos",
    "solicitudes_estudiantiles",
    "reuniones_actas_y_acuerdos",
    "finanzas_y_transparencia",
    "inventario",
    "documentos",
    "encuestas_y_votaciones",
]

WORKFLOW_STEPS = [
    {"phase": "intake", "agent_id": None},
    {"phase": "specify", "agent_id": "agent.product_owner"},
    {"phase": "architecture", "agent_id": "agent.architect"},
    {"phase": "database", "agent_id": "agent.database_designer"},
    {"phase": "api_design", "agent_id": "agent.backend_developer"},
    {"phase": "ui_design", "agent_id": "agent.frontend_developer"},
    {"phase": "implementation_plan", "agent_id": "agent.architect"},
    {"phase": "qa_plan", "agent_id": "agent.qa_engineer"},
    {"phase": "security_review", "agent_id": "agent.security_reviewer"},
    {"phase": "close", "agent_id": "agent.documenter"},
]

FORBIDDEN_ACTIONS = [
    "leer secretos",
    "desplegar a produccion",
    "modificar servicios externos",
    "escribir en bases de datos reales",
    "ejecutar comandos destructivos",
]

