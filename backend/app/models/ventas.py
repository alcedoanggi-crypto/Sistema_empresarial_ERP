from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import FetchedValue, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BorradoLogico, ConTimestamps

CENTAVO = Decimal("0.01")


def redondear(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, ROUND_HALF_UP)


class Cliente(ConTimestamps, BorradoLogico, Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo_identificacion: Mapped[str]
    identificacion: Mapped[str]
    nombre: Mapped[str]
    email: Mapped[str | None]
    telefono: Mapped[str | None]
    direccion: Mapped[str | None]


class _LineaVenta:
    """Cálculo común a las líneas de cotización y de orden de venta."""

    @property
    def bruto(self) -> Decimal:
        return redondear(self.cantidad * self.precio_unitario)

    @property
    def descuento(self) -> Decimal:
        return redondear(self.bruto * self.descuento_pct / 100)

    @property
    def subtotal(self) -> Decimal:
        return self.bruto - self.descuento

    @property
    def producto_nombre(self) -> str:
        return self.producto.nombre

    @property
    def sku(self) -> str:
        return self.producto.sku


class _DocumentoVenta:
    @property
    def cliente_nombre(self) -> str:
        return self.cliente.nombre

    @property
    def total(self) -> Decimal:
        """Neto sin IVA (el IVA se calcula al facturar, según aplica_iva de cada producto)."""
        return sum((d.subtotal for d in self.detalles), Decimal("0"))


class Cotizacion(_DocumentoVenta, ConTimestamps, BorradoLogico, Base):
    __tablename__ = "cotizaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(server_default=FetchedValue())
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    fecha_emision: Mapped[date] = mapped_column(server_default=FetchedValue())
    fecha_validez: Mapped[date]
    estado: Mapped[str] = mapped_column(default="borrador")
    notas: Mapped[str | None]
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    detalles: Mapped[list["CotizacionDetalle"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="CotizacionDetalle.id"
    )
    orden_venta: Mapped["OrdenVenta | None"] = relationship(back_populates="cotizacion", lazy="selectin")

    @property
    def orden_venta_numero(self) -> str | None:
        return self.orden_venta.numero if self.orden_venta else None


class CotizacionDetalle(_LineaVenta, Base):
    __tablename__ = "cotizaciones_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    cotizacion_id: Mapped[int] = mapped_column(ForeignKey("cotizaciones.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[int]
    precio_unitario: Mapped[Decimal]
    descuento_pct: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    producto: Mapped["Producto"] = relationship(lazy="joined")  # noqa: F821


class OrdenVenta(_DocumentoVenta, ConTimestamps, BorradoLogico, Base):
    __tablename__ = "ordenes_venta"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(server_default=FetchedValue())
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"))
    cotizacion_id: Mapped[int | None] = mapped_column(ForeignKey("cotizaciones.id"))
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"))
    estado: Mapped[str] = mapped_column(default="pendiente")
    fecha: Mapped[date] = mapped_column(server_default=FetchedValue())
    notas: Mapped[str | None]
    creado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    cliente: Mapped[Cliente] = relationship(lazy="joined")
    almacen: Mapped["Almacen"] = relationship(lazy="joined")  # noqa: F821
    cotizacion: Mapped[Cotizacion | None] = relationship(back_populates="orden_venta", lazy="select")
    detalles: Mapped[list["OrdenVentaDetalle"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="OrdenVentaDetalle.id"
    )
    factura: Mapped["Factura | None"] = relationship(back_populates="orden_venta", lazy="selectin")

    @property
    def almacen_nombre(self) -> str:
        return self.almacen.nombre

    @property
    def cotizacion_numero(self) -> str | None:
        return self.cotizacion.numero if self.cotizacion else None

    @property
    def factura_id(self) -> int | None:
        return self.factura.id if self.factura else None

    @property
    def factura_numero(self) -> str | None:
        return self.factura.numero if self.factura else None


class OrdenVentaDetalle(_LineaVenta, Base):
    __tablename__ = "ordenes_venta_detalle"

    id: Mapped[int] = mapped_column(primary_key=True)
    orden_venta_id: Mapped[int] = mapped_column(ForeignKey("ordenes_venta.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[int]
    precio_unitario: Mapped[Decimal]
    descuento_pct: Mapped[Decimal] = mapped_column(default=Decimal("0"))

    producto: Mapped["Producto"] = relationship(lazy="joined")  # noqa: F821


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(server_default=FetchedValue())
    orden_venta_id: Mapped[int] = mapped_column(ForeignKey("ordenes_venta.id"))
    fecha_emision: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    subtotal: Mapped[Decimal]
    descuento: Mapped[Decimal]
    iva: Mapped[Decimal]
    total: Mapped[Decimal]
    tasa_iva: Mapped[Decimal]
    estado: Mapped[str] = mapped_column(default="emitida")
    emitida_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    anulada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_anulacion: Mapped[datetime | None]
    motivo_anulacion: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue(), server_onupdate=FetchedValue())

    orden_venta: Mapped[OrdenVenta] = relationship(back_populates="factura", lazy="joined")

    @property
    def orden_venta_numero(self) -> str:
        return self.orden_venta.numero

    @property
    def cliente_id(self) -> int:
        return self.orden_venta.cliente_id

    @property
    def cliente_nombre(self) -> str:
        return self.orden_venta.cliente.nombre
