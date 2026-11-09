from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Existencia, Movimiento, OrdenCompra, Producto, Usuario
from app.models.ventas import redondear
from app.services.documentos import exigir_estado


def recibir_orden(db: Session, orden_id: int, usuario: Usuario) -> OrdenCompra:
    """Recepción de mercadería: entradas al kardex + costo promedio ponderado, en una transacción."""
    try:
        estado = db.execute(
            select(OrdenCompra.estado)
            .where(OrdenCompra.id == orden_id, OrdenCompra.deleted_at.is_(None))
            .with_for_update()
        ).scalar_one_or_none()
        if estado is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden de compra no encontrada")
        orden = db.get(OrdenCompra, orden_id, populate_existing=True)
        exigir_estado(orden, "aprobada", accion="recibir")

        ids = sorted(d.producto_id for d in orden.detalles)
        # Bloquea los productos (se actualizará su costo) en orden determinista
        productos = {
            p.id: p
            for p in db.scalars(
                select(Producto).where(Producto.id.in_(ids)).order_by(Producto.id).with_for_update(of=Producto)
            )
        }
        stock_actual = dict(
            db.execute(
                select(Existencia.producto_id, func.sum(Existencia.cantidad))
                .where(Existencia.producto_id.in_(ids))
                .group_by(Existencia.producto_id)
            ).all()
        )

        for d in orden.detalles:
            producto = productos[d.producto_id]
            stock = Decimal(stock_actual.get(d.producto_id, 0))
            # Costo promedio ponderado
            if stock + d.cantidad > 0:
                producto.precio_costo = redondear(
                    (stock * producto.precio_costo + d.cantidad * d.costo_unitario) / (stock + d.cantidad)
                )
            db.add(Movimiento(
                producto_id=d.producto_id,
                almacen_id=orden.almacen_id,
                tipo="entrada",
                origen="compra",
                cantidad=d.cantidad,
                costo_unitario=d.costo_unitario,
                documento=orden.numero,
                usuario_id=usuario.id,
            ))

        orden.estado = "recibida"
        orden.recibido_por = usuario.id
        orden.fecha_recepcion = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(orden)
    return orden
