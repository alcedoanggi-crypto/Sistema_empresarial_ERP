"""Utilidades compartidas por los documentos con líneas (OC, cotización, OV)."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Producto


def productos_vigentes(db: Session, ids: list[int]) -> dict[int, Producto]:
    productos = {
        p.id: p
        for p in db.scalars(
            select(Producto).where(Producto.id.in_(ids), Producto.deleted_at.is_(None), Producto.activo)
        )
    }
    faltan = sorted(set(ids) - productos.keys())
    if faltan:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Productos inexistentes o inactivos: {faltan}")
    return productos


def lineas_venta(db: Session, detalles_in, modelo_linea) -> list:
    """Construye líneas de venta; si no se envía precio se toma el precio de venta vigente."""
    productos = productos_vigentes(db, [d.producto_id for d in detalles_in])
    return [
        modelo_linea(
            producto_id=d.producto_id,
            cantidad=d.cantidad,
            precio_unitario=d.precio_unitario if d.precio_unitario is not None else productos[d.producto_id].precio_venta,
            descuento_pct=d.descuento_pct,
        )
        for d in detalles_in
    ]


def exigir_estado(doc, *estados: str, accion: str) -> None:
    if doc.estado not in estados:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede {accion} el documento {doc.numero}: está '{doc.estado}' (se requiere {' / '.join(estados)})",
        )
