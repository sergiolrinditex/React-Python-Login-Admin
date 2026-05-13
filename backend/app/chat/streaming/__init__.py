"""
Hilo People — Chat streaming sub-package.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-PKG)
Phase:  P02 Core Features (the motor)
Purpose: Re-exports the streaming router so chat/routers/__init__.py
         can include it with a single import.

Source refs:
  - task pack P02-S03-T002 §F.2 §D-CHATSTREAM-PKG
"""

from app.chat.streaming.router import router

__all__ = ["router"]
