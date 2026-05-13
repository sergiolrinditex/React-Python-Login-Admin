"""
Hilo People — Admin model-test subpackage.

WRITE_SET_DRIFT §D-MT-PKG (P02-S05-T002): Required Python package marker for the
backend/app/admin/model_test/ feature module. Not in declared write_set but
justified: without this file the Python import chain fails. Mirrors the pattern
used by §D-MCPWIRE (P02-S07-T001) and §D-AAP (P02-S05-T001).

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: Re-exports the model_test_router for registration in admin/__init__.py
         (P-22 aggregator pattern, §D-MT-WIRE).

Exported:
  model_test_router — APIRouter for POST /api/v1/admin/ai/models/{id}/test.
                      Included by admin/__init__.py under the admin_router.
"""

from app.admin.model_test.router import model_test_router

__all__ = ["model_test_router"]
