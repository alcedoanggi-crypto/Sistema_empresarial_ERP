"""KPIs del dashboard. Todas las cifras salen de las vistas de 03_vistas.sql,
así el dashboard y los reportes usan exactamente la misma definición."""
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session


def _uno(db: Session, sql: str, **params):
    return db.execute(text(sql), params).scalar() or 0


def _filas(db: Session, sql: str, **params) -> list[dict]:
    return [dict(r) for r in db.execute(text(sql), params).mappings()]


def _variacion(actual: Decimal, anterior: Decimal) -> float | None:
    if not anterior:
        return None
    return round(float((actual - anterior) / anterior * 100), 1)


def kpis(db: Session, dias_ranking: int = 90) -> dict:
    ventas_mes = Decimal(_uno(db, """
        SELECT total FROM v_ventas_mensuales WHERE mes = date_trunc('month', CURRENT_DATE)::date"""))
    ventas_mes_anterior = Decimal(_uno(db, """
        SELECT total FROM v_ventas_mensuales
         WHERE mes = (date_trunc('month', CURRENT_DATE) - INTERVAL '1 month')::date"""))
    facturas_mes = _uno(db, """
        SELECT num_facturas FROM v_ventas_mensuales WHERE mes = date_trunc('month', CURRENT_DATE)::date""")

    return {
        "ventas_mes": float(ventas_mes),
        "ventas_mes_anterior": float(ventas_mes_anterior),
        "variacion_ventas": _variacion(ventas_mes, ventas_mes_anterior),
        "facturas_mes": facturas_mes,
        "ticket_promedio": float(ventas_mes / facturas_mes) if facturas_mes else 0.0,
        "empleados_activos": _uno(db, "SELECT count(*) FROM empleados WHERE estado = 'activo' AND deleted_at IS NULL"),
        "stock_critico": _uno(db, "SELECT count(*) FROM v_stock_critico"),
        "valor_inventario": float(_uno(db, "SELECT sum(valor_inventario) FROM v_stock_productos")),
        "ordenes_compra_abiertas": _uno(db, """
            SELECT count(*) FROM ordenes_compra WHERE estado IN ('borrador','aprobada') AND deleted_at IS NULL"""),
        "solicitudes_pendientes": _uno(db, "SELECT count(*) FROM solicitudes WHERE estado = 'pendiente'"),
        "dias_ranking": dias_ranking,

        # Últimos 12 meses, rellenando con 0 los meses sin ventas
        "ventas_mensuales": _filas(db, """
            SELECT to_char(m.mes, 'YYYY-MM') AS mes,
                   COALESCE(v.total, 0)::float AS total,
                   COALESCE(v.num_facturas, 0) AS facturas
              FROM generate_series(date_trunc('month', CURRENT_DATE) - INTERVAL '11 months',
                                   date_trunc('month', CURRENT_DATE), INTERVAL '1 month') AS m(mes)
              LEFT JOIN v_ventas_mensuales v ON v.mes = m.mes::date
             ORDER BY m.mes"""),

        "top_productos": _filas(db, """
            SELECT producto_id, sku, producto, SUM(cantidad)::int AS unidades, SUM(importe)::float AS importe
              FROM v_lineas_vendidas
             WHERE fecha_emision >= CURRENT_DATE - make_interval(days => :dias)
             GROUP BY producto_id, sku, producto
             ORDER BY unidades DESC, importe DESC
             LIMIT 5""", dias=dias_ranking),

        "ventas_por_categoria": _filas(db, """
            SELECT categoria, SUM(importe)::float AS importe
              FROM v_lineas_vendidas
             WHERE fecha_emision >= CURRENT_DATE - make_interval(days => :dias)
             GROUP BY categoria ORDER BY importe DESC""", dias=dias_ranking),

        "productos_criticos": _filas(db, """
            SELECT producto_id, sku, nombre, stock_total, stock_minimo, estado_stock
              FROM v_stock_critico ORDER BY stock_total - stock_minimo, nombre LIMIT 8"""),

        "empleados_por_departamento": _filas(db, """
            SELECT d.nombre AS departamento, count(e.id)::int AS empleados
              FROM departamentos d
              JOIN puestos p   ON p.departamento_id = d.id
              JOIN empleados e ON e.puesto_id = p.id AND e.estado = 'activo' AND e.deleted_at IS NULL
             WHERE d.deleted_at IS NULL
             GROUP BY d.nombre ORDER BY empleados DESC"""),
    }
