"""
app/api/v1/__init__.py
-----------------------
Import tất cả routers của API v1 để main.py có thể include.
"""

from app.api.v1 import chat, history, ingest, search

__all__ = ["chat", "ingest", "history", "search"]
