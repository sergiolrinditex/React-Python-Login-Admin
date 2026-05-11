"""
Hilo People — backend dependency smoke test.

Slice:   P00-S01-T003 — Backend dependency pack
Phase:   P00 Scaffold + Design System
Purpose: Verifies that all backend dependencies declared in pyproject.toml
         (§2.0 Library Discovery Pass + §2.1 aux stack contract items) are
         importable and report a valid version string. This confirms the
         install is functional before any business logic uses these packages.

Test strategy:
  - Pure import + importlib.metadata.version() or module.__version__.
  - NO network calls, NO DB access, NO LLM calls.
  - ENABLE_VERBOSE_LOGGING=true  → logs BEFORE and AFTER each import.
  - ENABLE_VERBOSE_LOGGING=false → logs only failures (warning+error).

Verify cmd (from CHECKLIST):
  pytest backend/tests -k dependency_smoke

Write_set extension: backend/tests/ is not in the declared write_set for
T003 (backend/app/core/**, backend/pyproject.toml, backend/requirements*.txt).
This file is created under the same precedent as T001 (test_health.py) where
the tester-required verify command cannot be satisfied without a test file.
Flagged in handoff as WRITE_SET_DRIFT with validator pre-approval.

Dependencies:
  All packages listed in backend/pyproject.toml [project.dependencies] plus
  [project.optional-dependencies].test and .dev as declared in T003.
"""

import importlib.metadata
import logging
import os

import pytest

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
_VERBOSE = os.environ.get("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

logger = logging.getLogger(__name__)

if not logging.root.handlers:
    logging.basicConfig(
        level=logging.DEBUG if _VERBOSE else logging.WARNING,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _get_version(dist_name: str, module_attr: str | None = None, module=None) -> str:
    """
    Return version string for a distribution.

    Tries module.__version__ first (if module provided), then falls back to
    importlib.metadata.version(dist_name). This handles packages that do not
    expose __version__ directly (litellm, langgraph, pgvector, etc.).

    Parameters:
        dist_name:    PyPI distribution name (used for importlib.metadata).
        module_attr:  Dotted attribute path on the module object, or None.
        module:       Imported module object, or None.

    Returns:
        Version string such as "1.2.3".

    Raises:
        importlib.metadata.PackageNotFoundError if the package is not installed.
    """
    if module is not None and module_attr:
        try:
            val = module
            for part in module_attr.split("."):
                val = getattr(val, part)
            if isinstance(val, str) and val:
                return val
        except AttributeError:
            pass
    return importlib.metadata.version(dist_name)


# ---------------------------------------------------------------------------
# Parametrized smoke cases
# Each entry: (dist_name, import_stmt, version_attr_or_None)
# version_attr_or_None = dotted attribute on the top-level module, or None to
#   always use importlib.metadata.version(dist_name).
# ---------------------------------------------------------------------------

_SMOKE_CASES: list[tuple[str, str, str | None]] = [
    # (dist_name, import_module_as, module_version_attr)
    ("pypdf", "pypdf", "__version__"),
    ("python-docx", "docx", "__version__"),
    ("celery", "celery", "__version__"),
    ("redis", "redis", "__version__"),
    ("resend", "resend", "__version__"),
    ("structlog", "structlog", None),          # no __version__; use metadata
    ("prometheus-client", "prometheus_client", "__version__"),
    ("boto3", "boto3", "__version__"),
    ("pgvector", "pgvector", None),            # no __version__; use metadata
    ("litellm", "litellm", None),              # __version__ attr does not exist in 1.83.x
    ("langchain", "langchain", "__version__"),
    # langchain 1.x is a meta-package; the three split sub-packages must be
    # pinned explicitly (per researcher canonical note row 13) to prevent
    # transitive version drift. Each gets its own smoke case to keep
    # "1 pin == 1 smoke" symmetry.
    ("langchain-core", "langchain_core", "__version__"),
    ("langchain-community", "langchain_community", "__version__"),
    ("langchain-text-splitters", "langchain_text_splitters", None),  # no __version__; metadata
    ("langgraph", "langgraph", None),          # no __version__; use metadata
    ("deepagents", "deepagents", None),        # no __version__; use metadata
    ("mcp", "mcp", None),                      # no __version__; use metadata
    ("tiktoken", "tiktoken", None),            # no __version__; use metadata
    ("sqlalchemy", "sqlalchemy", "__version__"),
    ("alembic", "alembic", "__version__"),
]


@pytest.mark.parametrize("dist_name,import_name,version_attr", _SMOKE_CASES)
def test_dependency_smoke(dist_name: str, import_name: str, version_attr: str | None) -> None:
    """
    Smoke test: verify that a declared backend dependency is importable and
    reports a non-empty version string.

    Business rule (01-non-negotiables §Dependencies):
      Every declared package must be pinned to exact version. This test
      confirms the install is coherent — it does NOT test functionality, only
      importability and metadata availability.

    Logging policy (01-non-negotiables §Logging):
      BEFORE: log package name and dist name.
      AFTER:  log resolved version.
      ERROR:  log on import failure or missing version.
    """
    if _VERBOSE:
        logger.info(
            "[BEFORE] dependency_smoke: importing '%s' (dist='%s')",
            import_name,
            dist_name,
        )

    try:
        module = __import__(import_name)
    except ImportError as exc:
        logger.error(
            "[ERROR] dependency_smoke: failed to import '%s' — %s",
            import_name,
            exc,
        )
        pytest.fail(f"Cannot import '{import_name}' (dist={dist_name}): {exc}")
        return

    version = _get_version(dist_name, version_attr, module)

    assert version, (
        f"Package '{dist_name}' imported as '{import_name}' but reports no version. "
        f"Check importlib.metadata.version('{dist_name}')."
    )

    if _VERBOSE:
        logger.info(
            "[AFTER] dependency_smoke: '%s' OK — version=%s",
            import_name,
            version,
        )
    else:
        # Non-verbose: only failures appear; success is silent per non-negotiable.
        pass
