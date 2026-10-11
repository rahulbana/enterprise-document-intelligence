# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Importing every model here registers it on Base.metadata, which Alembic's
# env.py relies on for autogeneration. Import this package (not individual
# model modules) wherever "all models must be known" matters.

from app.models.auth_audit_log import AuthAuditLog, AuthEventType
from app.models.chat_memory import ChatMemory
from app.models.chat_message import ChatMessage, ChatMessageRole
from app.models.chat_session import ChatSession
from app.models.department import Department
from app.models.document import Document, DocumentVisibility
from app.models.document_department import document_departments
from app.models.document_version import DocumentVersion, IngestionStatus
from app.models.user import User
from app.models.user_department import user_departments

__all__ = [
    "AuthAuditLog",
    "AuthEventType",
    "ChatMemory",
    "ChatMessage",
    "ChatMessageRole",
    "ChatSession",
    "Department",
    "Document",
    "DocumentVersion",
    "DocumentVisibility",
    "IngestionStatus",
    "User",
    "document_departments",
    "user_departments",
]
