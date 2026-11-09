from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Text

from app.models.base import Base


class Auditoria(Base):
    """Sólo lectura: la escriben los triggers fn_auditoria."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    tabla: Mapped[str]
    registro_id: Mapped[int | None]
    accion: Mapped[str]
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    ip: Mapped[str | None] = mapped_column(INET)
    datos_anteriores: Mapped[dict | None] = mapped_column(JSONB)
    datos_nuevos: Mapped[dict | None] = mapped_column(JSONB)
    campos_modificados: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    fecha: Mapped[datetime]

    usuario: Mapped["Usuario | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def usuario_nombre(self) -> str | None:
        return self.usuario.nombre if self.usuario else None
