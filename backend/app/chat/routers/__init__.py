"""
Hilo People — Chat routers package.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Package marker for the chat routers sub-package.
         Re-exports the `router` for app/main.py mounting.
"""

from app.chat.routers.conversations import router

__all__ = ["router"]
