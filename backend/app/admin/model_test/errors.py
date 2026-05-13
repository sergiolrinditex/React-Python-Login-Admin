"""
Hilo People — Admin model-test domain errors.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: Typed domain errors for the model-test use case. These are raised
         by service.py and caught by router.py for HTTP translation.

         Keeps service.py ≤300 LoC by extracting the error class definitions.

Source refs:
  - task pack P02-S05-T002 §D.2.A (error taxonomy)
  - 01-non-negotiables.md §Error handling (typed domain errors)
"""

from __future__ import annotations


class ModelNotFoundError(Exception):
    """Raised when the requested AiModel UUID does not exist in ai_models.

    Router maps this to: 404 AI_MODEL_NOT_FOUND.
    """

    code = "AI_MODEL_NOT_FOUND"


class CredentialNotFoundError(Exception):
    """Raised when the model's provider has no ai_provider_credentials row.

    Router maps this to: 404 AI_PROVIDER_CREDENTIAL_NOT_FOUND.
    """

    code = "AI_PROVIDER_CREDENTIAL_NOT_FOUND"
