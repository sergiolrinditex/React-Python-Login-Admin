"""
Hilo People — Chat routers package.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints (initial)
        P02-S03-T002 — Chat streaming endpoint (extended: add streaming sub-router,
                       §D-CHATSTREAM-WIRE, §K-CHAT-AGG WRITE_SET_DRIFT)
Phase:  P02 Core Features (the motor)
Purpose: Aggregator for the chat routers sub-package.
         Re-exports the combined `router` (CRUD + streaming) for app/main.py mounting.
         The streaming sub-router is included under the same '/conversations' prefix
         so it resolves to /api/v1/chat/conversations/{id}/stream as declared in
         TECHNICAL_GUIDE §6.2 row 267.

Decisions:
  - D-CHATSTREAM-WIRE: extend THIS aggregator rather than touching app/main.py
    directly. Keeps the chat router family self-contained (P-22 pattern).
  - §K-CHAT-AGG: WRITE_SET_DRIFT anchor — adding the streaming include here is
    predeclared in task pack P02-S03-T002 §K.

Source refs:
  - task pack P02-S03-T002 §F.2 (§K-CHAT-AGG WRITE_SET_DRIFT)
  - task pack P02-S03-T002 §H D-CHATSTREAM-WIRE
"""

from fastapi import APIRouter

from app.chat.routers.conversations import router as _conversations_router
from app.chat.streaming.router import router as _streaming_router

router = APIRouter()
router.include_router(_conversations_router)
router.include_router(_streaming_router)

__all__ = ["router"]
