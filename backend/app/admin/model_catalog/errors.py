"""
Hilo People — Admin AI model catalog typed domain errors.

Slice:  P02-S05-T003 — Add partial unique index for is_default=true per model_type
Phase:  P02 Core Features
Purpose: Typed domain errors for the model catalog use cases. Domain errors
         must not import HTTP-layer primitives (FastAPI, Starlette) — they live
         in the domain layer and are translated to HTTP at the router boundary.

Key deps:
  - None (standalone leaf module — no external deps)

Source refs:
  - task pack P02-S05-T003 §C (service/router/errors spec)
  - 01-non-negotiables.md §Error handling (typed domain errors, not generic Exception)
  - Precedent: app/auth/services/sign_up.py EmailAlreadyExistsError → 409 pattern
"""

from __future__ import annotations


class ModelDefaultConflictError(Exception):
    """Raised when setting is_default=true would violate the D-DEF1 invariant.

    D-DEF1: at most one ai_models row per model_type may have is_default = true.
    This error is raised when the DB-level partial unique index
    'ai_models_default_per_type_uidx' rejects a concurrent PATCH that would
    create a second default for the same model_type.

    The service catches sqlalchemy.exc.IntegrityError for the specific constraint
    'ai_models_default_per_type_uidx' (pgcode 23505) and translates it to this
    typed domain error. The router maps it to HTTP 409 AI_MODEL_DEFAULT_CONFLICT.

    Attributes:
        model_type: The model_type for which the conflict occurred.

    Refs: task pack P02-S05-T003 §C, §A.5 (error envelope contract)
    """

    def __init__(self, model_type: str) -> None:
        """Initialize the conflict error.

        Args:
            model_type: The model_type that already has a default
                        (e.g. 'chat', 'embeddings').
        """
        super().__init__(
            f"A default model for model_type='{model_type}' already exists. "
            "Clear the existing default before setting a new one, or use a "
            "sequential (non-concurrent) operation."
        )
        self.model_type = model_type


__all__ = ["ModelDefaultConflictError"]
