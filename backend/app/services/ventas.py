"""Facturación: la operación crítica del sistema.

facturar() ejecuta TODO en una única transacción:

    1. Bloquea la orden de venta (SELECT ... FOR UPDATE) -> dos usuarios no
       pueden facturar la misma orden a la vez.
    2. Bloquea las filas de existencias involucradas, ordenadas por
       producto_id (orden fijo = sin deadlocks entre ventas concurrentes).
    3. Verifica stock suficiente y devuelve TODOS los faltantes juntos.
    4. Inserta la factura con totales calculados (IVA por producto).
    5. Inserta los movimientos de salida; el trigger fn_aplicar_movimiento
       descuenta existencias (y vuelve a validar que no quede negativo).
    6. Marca la orden como facturada (el trigger valida la transición).
    7. COMMIT. Si cualquier paso falla -> ROLLBACK: ni factura, ni movimientos,
       ni descuento de stock. Todo o nada.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Existencia, Factura, Movimiento, OrdenVenta, Usuario
from app.models.ventas import redondear
from app.services.documentos import exigir_estado


def calcular_totales(orden: OrdenVenta, tasa_iva: Decimal) -> dict[str, Decimal]:
    subtotal = sum((d.bruto for d in orden.detalles), Decimal("0"))
    descuento = sum((d.descuento for d in orden.detalles), Decimal("0"))
    base_iva = sum((d.subtotal for d in orden.detalles if d.producto.aplica_iva), Decimal("0"))
    iva = redondear(base_iva * tasa_iva / 100)
    return {
        "subtotal": subtotal,
        "descuento": descuento,
        "iva": iva,
        "total": subtotal - descuento + iva,
        "tasa_iva": tasa_iva,
    }


def facturar(db: Session, orden_id: int, usuario: Usuario) -> Factura:
    try:
        # 1. Bloqueo de la orden
        estado = db.execute(
            select(OrdenVenta.estado)
            .where(OrdenVenta.id == orden_id, OrdenVenta.deleted_at.is_(None))
            .with_for_update()
        ).scalar_one_or_none()
        if estado is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Orden de venta no encontrada")
        orden = db.get(OrdenVenta, orden_id, populate_existing=True)
        exigir_estado(orden, "pendiente", accion="facturar")

        # 2. Bloqueo de existencias en orden determinista
        requeridos = {d.producto_id: d.cantidad for d in orden.detalles}
        disponibles = dict(
            db.execute(
                select(Existencia.producto_id, Existencia.cantidad)
                .where(Existencia.almacen_id == orden.almacen_id, Existencia.producto_id.in_(requeridos))
                .order_by(Existencia.producto_id)
                .with_for_update()
            ).all()
        )

        # 3. Validación de stock (todas las líneas a la vez)
        faltantes = [
            {
                "producto_id": d.producto_id,
                "producto": d.producto.nombre,
                "solicitado": d.cantidad,
                "disponible": disponibles.get(d.producto_id, 0),
            }
            for d in orden.detalles
            if disponibles.get(d.producto_id, 0) < d.cantidad
        ]
        if faltantes:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {"mensaje": f"Stock insuficiente en {orden.almacen.nombre}", "faltantes": faltantes},
            )

        # 4. Factura
        factura = Factura(orden_venta_id=orden.id, emitida_por=usuario.id,
                          **calcular_totales(orden, settings.tasa_iva))
        db.add(factura)
        db.flush()  # obtiene el número generado por la secuencia

        # 5. Salidas de inventario (el trigger descuenta existencias)
        db.add_all(
            Movimiento(
                producto_id=d.producto_id,
                almacen_id=orden.almacen_id,
                tipo="salida",
                origen="venta",
                cantidad=d.cantidad,
                costo_unitario=d.producto.precio_costo,
                documento=factura.numero,
                usuario_id=usuario.id,
            )
            for d in orden.detalles
        )

        # 6. Estado de la orden
        orden.estado = "facturada"

        # 7. Todo o nada
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(factura)
    return factura


def anular_factura(db: Session, factura_id: int, motivo: str, usuario: Usuario) -> Factura:
    """Anula una factura y devuelve la mercadería al almacén (también atómico)."""
    try:
        estado = db.execute(
            select(Factura.estado).where(Factura.id == factura_id).with_for_update()
        ).scalar_one_or_none()
        if estado is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
        factura = db.get(Factura, factura_id, populate_existing=True)
        exigir_estado(factura, "emitida", accion="anular")

        orden = factura.orden_venta
        db.add_all(
            Movimiento(
                producto_id=d.producto_id,
                almacen_id=orden.almacen_id,
                tipo="entrada",
                origen="anulacion",
                cantidad=d.cantidad,
                costo_unitario=d.producto.precio_costo,
                documento=factura.numero,
                nota=f"Anulación: {motivo}",
                usuario_id=usuario.id,
            )
            for d in orden.detalles
        )
        factura.estado = "anulada"
        factura.anulada_por = usuario.id
        factura.fecha_anulacion = datetime.now(timezone.utc)
        factura.motivo_anulacion = motivo
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(factura)
    return factura
