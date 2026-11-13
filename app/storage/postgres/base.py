"""Declarative base shared by every ORM row class and by Alembic's autogenerate."""

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, MetaData, Text
from sqlalchemy.orm import DeclarativeBase

# Mirrors the names Postgres generates for unnamed constraints, so a database created by the
# old hand-rolled migrator and one created by Alembic have identical constraint names.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Plain `str` is `text` and `datetime` is `timestamptz` everywhere in this schema.
    type_annotation_map: ClassVar[dict[Any, Any]] = {str: Text, datetime: DateTime(timezone=True)}
