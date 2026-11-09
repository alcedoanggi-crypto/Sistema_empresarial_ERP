from app.models.base import Base
from app.models.seguridad import ACCIONES, Modulo, Permiso, Rol, Usuario
from app.models.rrhh import Asistencia, Departamento, Empleado, Puesto, Solicitud
from app.models.inventario import Almacen, Categoria, Existencia, Movimiento, Producto
from app.models.compras import OrdenCompra, OrdenCompraDetalle, Proveedor
from app.models.ventas import Cliente, Cotizacion, CotizacionDetalle, Factura, OrdenVenta, OrdenVentaDetalle
from app.models.auditoria import Auditoria

__all__ = [
    "Base", "ACCIONES", "Modulo", "Permiso", "Rol", "Usuario",
    "Asistencia", "Departamento", "Empleado", "Puesto", "Solicitud",
    "Almacen", "Categoria", "Existencia", "Movimiento", "Producto",
    "OrdenCompra", "OrdenCompraDetalle", "Proveedor",
    "Cliente", "Cotizacion", "CotizacionDetalle", "Factura", "OrdenVenta", "OrdenVentaDetalle",
    "Auditoria",
]
