"""ORM row classes: the single source of truth for the schema (Alembic reads `Base.metadata`).

Importing this package registers every table on `Base.metadata`; add new rows to the imports.
"""

from app.storage.postgres.models.user import UserRow

__all__ = ["UserRow"]
