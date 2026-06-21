"""Utilidades de observabilidad con logs JSONL."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import utc_now_iso


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": utc_now_iso(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

