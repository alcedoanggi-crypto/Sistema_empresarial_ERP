from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.comun import ORM, Dinero, MontoEntrada

UnidadMedida = Literal["UND", "KG", "LT", "MT", "CAJA", "PAQ"]


class CategoriaCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(None, max_length=250)


class CategoriaActualizar(BaseModel):
    nombre: str | None = Field(None, min_length=2, max_length=80)
    descripcion: str | None = Field(None, max_length=250)


class CategoriaOut(ORM):
    id: int
    nombre: str
    descripcion: str | None


class AlmacenCrear(BaseModel):
    codigo: str = Field(min_length=2, max_length=10)
    nombre: str = Field(min_length=2, max_length=80)
    direccion: str | None = Field(None, max_length=200)
    activo: bool = True


class AlmacenActualizar(BaseModel):
    codigo: str | None = Field(None, min_length=2, max_length=10)
    nombre: str | None = Field(None, min_length=2, max_length=80)
    direccion: str | None = Field(None, max_length=200)
    activo: bool | None = None


class AlmacenOut(ORM):
    id: int
    codigo: str
    nombre: str
    direccion: str | None
    activo: bool


class ProductoCrear(BaseModel):
    sku: str = Field(pattern=r"^[A-Z0-9-]{3,30}$")
    nombre: str = Field(min_length=2, max_length=120)
    descripcion: str | None = Field(None, max_length=500)
    categoria_id: int
    unidad_medida: UnidadMedida = "UND"
    precio_costo: MontoEntrada
    precio_venta: MontoEntrada
    aplica_iva: bool = True
    stock_minimo: int = Field(0, ge=0)
    activo: bool = True


class ProductoActualizar(BaseModel):
    sku: str | None = Field(None, pattern=r"^[A-Z0-9-]{3,30}$")
    nombre: str | None = Field(None, min_length=2, max_length=120)
    descripcion: str | None = Field(None, max_length=500)
    categoria_id: int | None = None
    unidad_medida: UnidadMedida | None = None
    precio_costo: MontoEntrada | None = None
    precio_venta: MontoEntrada | None = None
    aplica_iva: bool | None = None
    stock_minimo: int | None = Field(None, ge=0)
    activo: bool | None = None


class ProductoOut(ORM):
    id: int
    sku: str
    nombre: str
    descripcion: str | None
    categoria_id: int
    categoria_nombre: str
    unidad_medida: str
    precio_costo: Dinero
    precio_venta: Dinero
    aplica_iva: bool
    stock_minimo: int
    stock_total: int
    activo: bool


class StockOut(BaseModel):
    producto_id: int
    sku: str
    nombre: str
    categoria: str
    unidad_medida: str
    stock_minimo: int
    stock_total: int
    precio_costo: Dinero
    valor_inventario: Dinero
    estado_stock: str


class ExistenciaAlmacenOut(BaseModel):
    almacen_id: int
    almacen: str
    cantidad: int


class MovimientoCrear(BaseModel):
    """Ajuste manual de inventario (conteo físico, merma, etc.)."""
    producto_id: int
    almacen_id: int
    tipo: Literal["entrada", "salida"]
    cantidad: int = Field(gt=0)
    nota: str = Field(min_length=3, max_length=250)


class MovimientoOut(ORM):
    id: int
    producto_id: int
    sku: str
    producto_nombre: str
    almacen_id: int
    almacen_nombre: str
    tipo: str
    origen: str
    cantidad: int
    costo_unitario: Dinero | None
    documento: str | None
    nota: str | None
    usuario_nombre: str | None
    created_at: datetime
