from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.comun import ORM, Dinero, MontoEntrada


class ProveedorCrear(BaseModel):
    ruc: str = Field(pattern=r"^[0-9]{13}$")
    razon_social: str = Field(min_length=3, max_length=150)
    nombre_contacto: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=200)
    dias_credito: int = Field(0, ge=0, le=180)


class ProveedorActualizar(BaseModel):
    ruc: str | None = Field(None, pattern=r"^[0-9]{13}$")
    razon_social: str | None = Field(None, min_length=3, max_length=150)
    nombre_contacto: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=200)
    dias_credito: int | None = Field(None, ge=0, le=180)


class ProveedorOut(ORM):
    id: int
    ruc: str
    razon_social: str
    nombre_contacto: str | None
    email: str | None
    telefono: str | None
    direccion: str | None
    dias_credito: int


class LineaCompraIn(BaseModel):
    producto_id: int
    cantidad: int = Field(gt=0)
    costo_unitario: MontoEntrada


class OrdenCompraIn(BaseModel):
    proveedor_id: int
    almacen_id: int
    fecha_entrega_esperada: date | None = None
    notas: str | None = Field(None, max_length=500)
    detalles: list[LineaCompraIn] = Field(min_length=1)

    @field_validator("detalles")
    @classmethod
    def sin_repetidos(cls, v):
        ids = [d.producto_id for d in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Un producto no puede repetirse en la orden")
        return v


class LineaCompraOut(ORM):
    id: int
    producto_id: int
    sku: str
    producto_nombre: str
    cantidad: int
    costo_unitario: Dinero
    subtotal: Dinero


class OrdenCompraOut(ORM):
    id: int
    numero: str
    proveedor_id: int
    proveedor_nombre: str
    almacen_id: int
    almacen_nombre: str
    estado: str
    fecha_emision: date
    fecha_entrega_esperada: date | None
    notas: str | None
    total: Dinero
    aprobado_por: int | None
    fecha_aprobacion: datetime | None
    fecha_recepcion: datetime | None
    created_at: datetime


class OrdenCompraDetalleOut(OrdenCompraOut):
    detalles: list[LineaCompraOut]
