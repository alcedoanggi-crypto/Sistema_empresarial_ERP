from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import FetchedValue, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BorradoLogico, ConTimestamps


class Proveedor(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    ruc: Mapped[str]
    razon_social: Mapped[str]
    nombre_contacto: Mapped[str | None]
    email: Mapped[str | None]
    telefono: Mapped[str | None]
    direccion: Mapped[str | None]
    dias_credito: Mapped[int] = mapped_column(default=0)


class OrdenCompra(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "ordenes_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(server_default=FetchedValue())
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedores.id"))
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"))
    estado: Mapped[str] = mapped_column(default="borrador")
    fecha_emision: Mapped[date] = mapped_column(server_default=FetchedValue())
    fecha_entrega_esperada: Mapped[date | None]
    notas: Mapped[str | None]
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    aprobado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_aprobacion: Mapped[datetime | None]
    recibido_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_recepcion: Mapped[datetime | None]

    proveedor: Mapped[Proveedor] = relationship(lazy="joined")
    almacen: Mapped["Almacen"] = relationship(lazy="joined")  # noqa: F821
    detalles: Mapped[list["OrdenCompraDetalle"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="OrdenCompraDetalle.id"
    )

    @property
    def proveedor_nombre(self) -> str:
        return self.proveedor.razon_social

    @property
    def almacen_nombre(self) -> str:
        return self.almacen.nombre

    @property
    def total(self) -> Decimal:
        return sum((d.subtotal for d in self.detalles), Decimal("0"))


class OrdenCompraDetalle(Base):
    __tablename__ = "ordenes_compra_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    orden_compra_id: Mapped[int] = mapped_column(ForeignKey("ordenes_compra.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[int]
    costo_unitario: Mapped[Decimal]

    producto: Mapped["Producto"] = relationship(lazy="joined")  # noqa: F821

    @property
    def producto_nombre(self) -> str:
        return self.producto.nombre

    @property
    def sku(self) -> str:
        return self.producto.sku

    @property
    def subtotal(self) -> Decimal:
        return self.cantidad * self.costo_unitario
