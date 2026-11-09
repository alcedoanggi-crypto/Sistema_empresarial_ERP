from datetime import datetime

from sqlalchemy import FetchedValue
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Las tablas se crean con sql/*.sql (fuente de verdad). Estos modelos sólo las mapean."""


class ConTimestamps:
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue(), server_onupdate=FetchedValue())


class BorradoLogico:
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
