"""Context-pack minimo para una ejecucion de fabrica."""

from __future__ import annotations

from typing import Any

from .constants import PRODUCT_MODULES, PRODUCT_NAME, WORKFLOW_STEPS


def build_context_pack(objective: str) -> dict[str, Any]:
    return {
        "product_name": PRODUCT_NAME,
        "objective": objective,
        "modules": list(PRODUCT_MODULES),
        "workflow": list(WORKFLOW_STEPS),
        "stage": "factory_bootstrap",
        "implementation_boundary": "No backend/frontend implementation in this stage.",
    }

