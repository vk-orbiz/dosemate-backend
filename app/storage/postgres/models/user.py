from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.postgres.base import Base


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[datetime]
