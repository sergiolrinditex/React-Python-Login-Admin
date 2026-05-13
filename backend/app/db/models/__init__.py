"""
Hilo People — ORM models sub-package.

Slice:  P02-S01-T001 — 0002_ai_chat_rag_mcp_agents migration
Phase:  P02 Core Features (the motor)
Purpose: Imports all model modules so their classes register with Base.metadata
         when this package is imported. Alembic env.py imports app.db which
         imports this package, ensuring every mapped table is known to metadata
         before autogenerate or upgrade/downgrade runs.

Modules added in P02-S01-T001:
  - chat.py       — Conversation, Message, MessageCitation (chat bounded context)
  - admin_ai.py   — AiProvider, AiProviderCredential, AiModel, AiModelTest,
                    LlmUsageLog (admin AI / LiteLLM gateway)
  - rag.py        — RagCollection, Document, DocumentVersion, DocumentChunk,
                    DocumentEmbedding, VectorizationJob (RAG admin + retrieval)
  - mcp.py        — McpServer, McpCredential, McpTool, McpResource, McpPrompt
                    (MCP server catalog)
  - agents.py     — Agent, McpAgentBinding, AgentRun, McpToolInvocation,
                    McpApproval (agent runtime + approval workflow)

Split decision (D.2): mcp_agents.py would exceed ~300 LOC with 10 models;
split by sub-bounded-context into mcp.py (server catalog) + agents.py (runtime).
Documented as WRITE_SET_DRIFT minor; write_set is backend/app/db/models/**.

Key deps:
  - app.db.base  — Base declarative class
  - sqlalchemy==2.0.49
  - pgvector==0.4.2 (imported via rag.py for VECTOR type)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 DB Schema
  - WRITE_SET_EXTENSION: package marker required for module discovery; same
    pattern as app/core/__init__.py (P00-S01-T003), extended P02-S01-T001.
"""

from app.db.models import user as _user_models  # noqa: F401 — registers User, EmployeeProfile, Role, Permission, UserRole
from app.db.models import auth as _auth_models  # noqa: F401 — registers RefreshToken, MfaTotpSecret, PasswordResetToken, AuditLog
from app.db.models import chat as _chat_models  # noqa: F401 — registers Conversation, Message, MessageCitation
from app.db.models import admin_ai as _admin_ai_models  # noqa: F401 — registers AiProvider, AiProviderCredential, AiModel, AiModelTest, LlmUsageLog
from app.db.models import rag as _rag_models  # noqa: F401 — registers RagCollection, Document, DocumentVersion, DocumentChunk, DocumentEmbedding, VectorizationJob
from app.db.models import mcp as _mcp_models  # noqa: F401 — registers McpServer, McpCredential, McpTool, McpResource, McpPrompt
from app.db.models import agents as _agents_models  # noqa: F401 — registers Agent, McpAgentBinding, AgentRun, McpToolInvocation, McpApproval

__all__ = [
    "_user_models",
    "_auth_models",
    "_chat_models",
    "_admin_ai_models",
    "_rag_models",
    "_mcp_models",
    "_agents_models",
]
