from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class UserRole(str, PyEnum):
    ADMIN    = "admin"
    REVIEWER = "reviewer"
    VIEWER   = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    username:        Mapped[str]           = mapped_column(String(64), nullable=False, unique=True)
    display_name:    Mapped[str]           = mapped_column(String(128), nullable=False)
    hashed_password: Mapped[str]           = mapped_column(String(256), nullable=False)
    department:      Mapped[str | None]    = mapped_column(String(128))
    role:            Mapped[UserRole]      = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        default=UserRole.VIEWER, nullable=False
    )
    is_active:       Mapped[bool]          = mapped_column(default=True, nullable=False)
    last_login_at:   Mapped[datetime | None] = mapped_column(DateTime)
