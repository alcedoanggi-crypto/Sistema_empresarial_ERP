import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.comun import ORM, Dinero, MontoEntrada

TipoIdentificacion = Literal["cedula", "ruc", "pasaporte"]
_PATRON_ID = {"cedula": r"^\d{10}$", "ruc": r"^\d{13}$", "pasaporte": r"^[A-Z0-9]{5,13}$"}


class ClienteCrear(BaseModel):
    tipo_identificacion: TipoIdentificacion
    identificacion: str = Field(min_length=5, max_length=13)
    nombre: str = Field(min_length=3, max_length=150)
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def identificacion_valida(self):
        if not re.match(_PATRON_ID[self.tipo_identificacion], self.identificacion):
            raise ValueError("La identificación no coincide con su tipo (cédula 10 dígitos, RUC 13)")
        return self


class ClienteActualizar(BaseModel):
    tipo_identificacion: TipoIdentificacion | None = None
    identificacion: str | None = Field(None, min_length=5, max_length=13)
    nombre: str | None = Field(None, min_length=3, max_length=150)
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=200)


class ClienteOut(ORM):
    id: int
    tipo_identificacion: str
    identificacion: str
    nombre: str
    email: str | None
    telefono: str | None
    direccion: str | None


# ---- Líneas comunes ------------------------------------------------------
class LineaVentaIn(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0)
    precio_unitario: MontoEntrada | None = Field(None, description="Por defecto, el precio de venta vigente")
    descuento_pct: Decimal = Field(Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)


def _sin_repetidos(v: list[LineaVentaIn]):
    ids = [d.producto_id for d in v]
    if len(ids) != len(set(ids)):
        raise ValueError("Un producto no puede repetirse en el documento")
    return v


class LineaVentaOut(ORM):
    id: int
    producto_id: int
    sku: str
    producto_nombre: str
    cantidad: int
    precio_unitario: Dinero
    descuento_pct: Dinero
    subtotal: Dinero


# ---- Cotizaciones --------------------------------------------------------
class CotizacionIn(BaseModel):
    cliente_id: int
    fecha_validez: date
    notas: str | None = Field(None, max_length=500)
    detalles: list[LineaVentaIn] = Field(min_length=1)

    @field_validator("detalles")
    @classmethod
    def sin_repetidos(cls, v):
        return _sin_repetidos(v)


class CotizacionOut(ORM):
    id: int
    numero: str
    cliente_id: int
    cliente_nombre: str
    fecha_emision: date
    fecha_validez: date
    estado: str
    notas: str | None
    total: Dinero
    orden_venta_numero: str | None
    created_at: datetime


class CotizacionDetalleOut(CotizacionOut):
    detalles: list[LineaVentaOut]


class ConvertirCotizacionIn(BaseModel):
    almacen_id: int


# ---- Órdenes de venta ----------------------------------------------------
class OrdenVentaIn(BaseModel):
    cliente_id: int
    almacen_id: int
    notas: str | None = Field(None, max_length=500)
    detalles: list[LineaVentaIn] = Field(min_length=1)

    @field_validator("detalles")
    @classmethod
    def sin_repetidos(cls, v):
        return _sin_repetidos(v)


class OrdenVentaOut(ORM):
    id: int
    numero: str
    cliente_id: int
    cliente_nombre: str
    cotizacion_id: int | None
    almacen_id: int
    almacen_nombre: str
    estado: str
    fecha: date
    notas: str | None
    total: Dinero
    factura_id: int | None
    factura_numero: str | None
    created_at: datetime


class OrdenVentaDetalleOut(OrdenVentaOut):
    cotizacion_numero: str | None
    detalles: list[LineaVentaOut]


# ---- Facturas ------------------------------------------------------------
class FacturaOut(ORM):
    id: int
    numero: str
    orden_venta_id: int
    orden_venta_numero: str
    cliente_id: int
    cliente_nombre: str
    fecha_emision: datetime
    subtotal: Dinero
    descuento: Dinero
    iva: Dinero
    total: Dinero
    tasa_iva: Dinero
    estado: str
    fecha_anulacion: datetime | None
    motivo_anulacion: str | None


class AnulacionIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)


class FaltanteStock(BaseModel):
    producto_id: int
    producto: str
    solicitado: int
    disponible: int
