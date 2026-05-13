"""
Hilo People — Chat module package.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Package marker for the chat bounded context. Re-exports the chat APIRouter
         for mounting in app/main.py.

Sub-packages:
  - chat.schemas          — Pydantic v2 DTOs
  - chat.errors           — typed domain errors
  - chat.cursor           — cursor encode/decode helpers
  - chat.repositories/    — SQLAlchemy queries
  - chat.services/        — use cases (one per file)
  - chat.routers/         — FastAPI APIRouter

Key deps:
  - app.db.models.chat    — Conversation, Message, MessageCitation ORM models
  - app.users.deps        — get_current_user dependency
  - app.db.session        — get_db_session
"""

from app.chat.routers import router as chat_router

__all__ = ["chat_router"]
