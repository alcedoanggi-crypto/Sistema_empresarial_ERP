from datetime import datetime
from decimal import Decimal

from sqlalchemy import FetchedValue, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BorradoLogico, ConTimestamps


class Categoria(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    descripcion: Mapped[str | None]


class Producto(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str]
    nombre: Mapped[str]
    descripcion: Mapped[str | None]
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"))
    unidad_medida: Mapped[str] = mapped_column(default="UND")
    precio_costo: Mapped[Decimal]
    precio_venta: Mapped[Decimal]
    aplica_iva: Mapped[bool] = mapped_column(default=True)
    stock_minimo: Mapped[int] = mapped_column(default=0)
    activo: Mapped[bool] = mapped_column(default=True)

    categoria: Mapped[Categoria] = relationship(lazy="joined")
    existencias: Mapped[list["Existencia"]] = relationship(lazy="selectin", viewonly=True)

    @property
    def categoria_nombre(self) -> str:
        return self.categoria.nombre

    @property
    def stock_total(self) -> int:
        return sum(e.cantidad for e in self.existencias)


class Almacen(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "almacenes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str]
    nombre: Mapped[str]
    direccion: Mapped[str | None]
    activo: Mapped[bool] = mapped_column(default=True)


class Existencia(Base):
    """Sólo lectura desde la aplicación: la mantiene el trigger fn_aplicar_movimiento."""

    __tablename__ = "existencias"

    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), primary_key=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), primary_key=True)
    cantidad: Mapped[int]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Movimiento(Base):
    __tablename__ = "movimientos_inventario"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"))
    tipo: Mapped[str]
    origen: Mapped[str]
    cantidad: Mapped[int]
    costo_unitario: Mapped[Decimal | None]
    documento: Mapped[str | None]
    nota: Mapped[str | None]
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())

    producto: Mapped[Producto] = relationship(lazy="joined")
    almacen: Mapped[Almacen] = relationship(lazy="joined")
    usuario: Mapped["Usuario | None"] = relationship(lazy="joined")  # noqa: F821

    @property
    def producto_nombre(self) -> str:
        return self.producto.nombre

    @property
    def sku(self) -> str:
        return self.producto.sku

    @property
    def almacen_nombre(self) -> str:
        return self.almacen.nombre

    @property
    def usuario_nombre(self) -> str | None:
        return self.usuario.nombre if self.usuario else None
