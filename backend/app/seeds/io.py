"""
I/O helpers for the seed bundle: load, validate, and parse JSON fixtures.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Provides a single public function load_fixture() that:
  1. Opens <source>/<namespace>/<filename>.json.
  2. Validates the file is parseable JSON (fail-fast on corrupt data).
  3. Returns the parsed dict for the caller to hand to a Pydantic schema.

Error messages always include the absolute file path and the missing/invalid
field, so operators know exactly which fixture to fix.

Dependencies:
  - pydantic 2.12.5 (callers pass the model class)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.logging import get_logger

_logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class BundleLoadError(Exception):
    """Raised when a fixture cannot be loaded or does not pass schema validation.

    Attributes:
      file_path — absolute path of the failing fixture.
      detail    — human-readable reason (field errors, parse error, etc.).
    """

    def __init__(self, file_path: Path, detail: str) -> None:
        self.file_path = file_path
        self.detail = detail
        super().__init__(f"Bundle load error [{file_path}]: {detail}")


def load_fixture(
    source_dir: Path,
    namespace: str,
    filename: str,
    model_cls: type[T],
) -> T:
    """Load and validate a single JSON fixture file.

    Purpose: central entry point so all fixture loading is consistent and
             error messages always carry the full file path + field name.

    Params:
      source_dir  — root verification bundle directory (e.g. data/verification/).
      namespace   — subdirectory within the bundle (e.g. 'users', 'auth').
      filename    — JSON file name including extension (e.g. 'employee_primary.json').
      model_cls   — Pydantic BaseModel subclass to validate against.
    Returns: validated model instance.
    Errors:
      BundleLoadError if the file does not exist, cannot be parsed as JSON,
      or fails Pydantic validation.
    """
    file_path = source_dir / namespace / filename
    _logger.debug(
        "BEFORE load_fixture: reading file",
        namespace=namespace,
        filename=filename,
    )

    if not file_path.exists():
        raise BundleLoadError(
            file_path,
            f"Required fixture file not found. Namespace '{namespace}' requires '{filename}'.",
        )

    raw: Any
    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleLoadError(
            file_path,
            f"JSON parse error at line {exc.lineno}, col {exc.colno}: {exc.msg}",
        ) from exc

    # Strip _comment fields at the top level (JSON doc convention) before
    # handing to Pydantic — models use extra="forbid" so unrecognised keys fail.
    if isinstance(raw, dict):
        raw = {k: v for k, v in raw.items() if not k.startswith("_")}

    try:
        result = model_cls.model_validate(raw)
    except ValidationError as exc:
        # Format field errors clearly: each error shows the field path + message.
        error_lines = []
        for e in exc.errors():
            loc = " -> ".join(str(p) for p in e["loc"])
            error_lines.append(f"  [{loc}] {e['msg']}")
        raise BundleLoadError(
            file_path,
            "Schema validation failed:\n" + "\n".join(error_lines),
        ) from exc

    _logger.debug(
        "AFTER load_fixture: validated",
        namespace=namespace,
        filename=filename,
        model=model_cls.__name__,
    )
    return result


def check_bundle_dir(source_dir: Path) -> None:
    """Verify the bundle root directory exists.

    Purpose: fail-fast with exit-2 semantics when --source points at
             a non-existent directory.
    Params:
      source_dir — path to the bundle root.
    Errors: raises FileNotFoundError if the directory does not exist.
    """
    if not source_dir.is_dir():
        raise FileNotFoundError(
            f"Verification bundle directory not found: {source_dir}\n"
            "Expected a directory with sub-folders: users/, auth/, rag/, "
            "admin_ai/, mcp_agents/, history/"
        )
