from datetime import datetime

from sqlalchemy import FetchedValue, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BorradoLogico, ConTimestamps

ACCIONES = ("ver", "crear", "editar", "eliminar", "aprobar")


class Rol(ConTimestamps, Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    descripcion: Mapped[str | None]
    es_sistema: Mapped[bool] = mapped_column(default=False)

    permisos: Mapped[list["Permiso"]] = relationship(
        back_populates="rol", lazy="selectin", cascade="all, delete-orphan"
    )


class Modulo(Base):
    __tablename__ = "modulos"

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str]
    nombre: Mapped[str]
    orden: Mapped[int] = mapped_column(default=0)


class Permiso(Base):
    __tablename__ = "permisos"

    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("modulos.id"), primary_key=True)
    puede_ver: Mapped[bool] = mapped_column(default=False)
    puede_crear: Mapped[bool] = mapped_column(default=False)
    puede_editar: Mapped[bool] = mapped_column(default=False)
    puede_eliminar: Mapped[bool] = mapped_column(default=False)
    puede_aprobar: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue(), server_onupdate=FetchedValue())

    rol: Mapped[Rol] = relationship(back_populates="permisos")
    modulo: Mapped[Modulo] = relationship(lazy="joined")


class Usuario(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    email: Mapped[str]
    password_hash: Mapped[str]
    rol_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    empleado_id: Mapped[int | None] = mapped_column(ForeignKey("empleados.id"))
    activo: Mapped[bool] = mapped_column(default=True)
    ultimo_acceso: Mapped[datetime | None]

    rol: Mapped[Rol] = relationship(lazy="joined")
    empleado: Mapped["Empleado | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def rol_nombre(self) -> str:
        return self.rol.nombre

    @property
    def empleado_nombre(self) -> str | None:
        return self.empleado.nombre_completo if self.empleado else None

    def permisos_dict(self) -> dict[str, dict[str, bool]]:
        return {
            p.modulo.clave: {a: getattr(p, f"puede_{a}") for a in ACCIONES}
            for p in self.rol.permisos
        }

    def puede(self, modulo: str, accion: str) -> bool:
        return any(p.modulo.clave == modulo and getattr(p, f"puede_{accion}") for p in self.rol.permisos)
