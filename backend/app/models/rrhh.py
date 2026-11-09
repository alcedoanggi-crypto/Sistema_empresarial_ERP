from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BorradoLogico, ConTimestamps


class Departamento(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "departamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str]
    nombre: Mapped[str]
    descripcion: Mapped[str | None]


class Puesto(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "puestos"

    id: Mapped[int] = mapped_column(primary_key=True)
    departamento_id: Mapped[int] = mapped_column(ForeignKey("departamentos.id"))
    nombre: Mapped[str]
    salario_min: Mapped[Decimal]
    salario_max: Mapped[Decimal]

    departamento: Mapped[Departamento] = relationship(lazy="joined")

    @property
    def departamento_nombre(self) -> str:
        return self.departamento.nombre


class Empleado(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "empleados"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str]
    cedula: Mapped[str]
    nombres: Mapped[str]
    apellidos: Mapped[str]
    email: Mapped[str]
    telefono: Mapped[str | None]
    direccion: Mapped[str | None]
    fecha_nacimiento: Mapped[date]
    fecha_ingreso: Mapped[date]
    fecha_salida: Mapped[date | None]
    puesto_id: Mapped[int] = mapped_column(ForeignKey("puestos.id"))
    jefe_id: Mapped[int | None] = mapped_column(ForeignKey("empleados.id"))
    salario: Mapped[Decimal]
    dias_vacaciones_anuales: Mapped[int] = mapped_column(default=15)
    estado: Mapped[str] = mapped_column(default="activo")

    puesto: Mapped[Puesto] = relationship(lazy="joined")
    jefe: Mapped["Empleado | None"] = relationship(remote_side="Empleado.id", lazy="select")

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}"

    @property
    def puesto_nombre(self) -> str:
        return self.puesto.nombre

    @property
    def departamento_id(self) -> int:
        return self.puesto.departamento_id

    @property
    def departamento_nombre(self) -> str:
        return self.puesto.departamento.nombre

    @property
    def jefe_nombre(self) -> str | None:
        return self.jefe.nombre_completo if self.jefe else None


class Asistencia(ConTimestamps, Base):
    __tablename__ = "asistencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int] = mapped_column(ForeignKey("empleados.id"))
    fecha: Mapped[date]
    hora_entrada: Mapped[time]
    hora_salida: Mapped[time | None]
    observacion: Mapped[str | None]

    empleado: Mapped[Empleado] = relationship(lazy="joined")

    @property
    def empleado_nombre(self) -> str:
        return self.empleado.nombre_completo

    @property
    def atraso(self) -> bool:
        return self.hora_entrada > time(8, 15)


class Solicitud(ConTimestamps, Base):
    __tablename__ = "solicitudes"

    id: Mapped[int] = mapped_column(primary_key=True)
    empleado_id: Mapped[int] = mapped_column(ForeignKey("empleados.id"))
    tipo: Mapped[str]
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date]
    dias: Mapped[int]
    motivo: Mapped[str]
    estado: Mapped[str] = mapped_column(default="pendiente")
    revisado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_revision: Mapped[datetime | None]
    comentario_revision: Mapped[str | None]

    empleado: Mapped[Empleado] = relationship(lazy="joined")
    revisor: Mapped["Usuario | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def empleado_nombre(self) -> str:
        return self.empleado.nombre_completo

    @property
    def revisor_nombre(self) -> str | None:
        return self.revisor.nombre if self.revisor else None
