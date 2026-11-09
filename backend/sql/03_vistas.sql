-- =====================================================================
--  Vistas
--
--  ¿Por qué vistas?
--    * Encapsulan consultas con varios JOIN/agregados en un solo nombre:
--      el dashboard, los reportes y la API consultan la MISMA definición de
--      "stock crítico" o "venta del mes", así no hay dos fórmulas distintas.
--    * Mantienen el modelo en 3FN (los totales se calculan, no se duplican)
--      sin que la aplicación tenga que repetir el cálculo.
--    * Son una capa de seguridad: se puede dar SELECT sobre la vista a un
--      rol de reportería sin exponer las tablas base.
-- =====================================================================

-- Stock consolidado de cada producto (todos los almacenes) y su semáforo
CREATE OR REPLACE VIEW v_stock_productos AS
SELECT p.id                                   AS producto_id,
       p.sku,
       p.nombre,
       c.nombre                               AS categoria,
       p.unidad_medida,
       p.stock_minimo,
       COALESCE(SUM(e.cantidad), 0)::INTEGER  AS stock_total,
       p.precio_costo,
       (COALESCE(SUM(e.cantidad), 0) * p.precio_costo)::NUMERIC(14,2) AS valor_inventario,
       CASE
           WHEN COALESCE(SUM(e.cantidad), 0) = 0              THEN 'agotado'
           WHEN COALESCE(SUM(e.cantidad), 0) <= p.stock_minimo THEN 'critico'
           ELSE 'normal'
       END                                    AS estado_stock
  FROM productos p
  JOIN categorias c ON c.id = p.categoria_id
  LEFT JOIN existencias e ON e.producto_id = p.id
 WHERE p.deleted_at IS NULL AND p.activo
 GROUP BY p.id, c.nombre;

-- Alertas de stock mínimo
CREATE OR REPLACE VIEW v_stock_critico AS
SELECT * FROM v_stock_productos
 WHERE estado_stock IN ('agotado','critico');

-- Ventas facturadas por mes
CREATE OR REPLACE VIEW v_ventas_mensuales AS
SELECT date_trunc('month', f.fecha_emision)::DATE AS mes,
       COUNT(*)                                   AS num_facturas,
       SUM(f.subtotal - f.descuento)              AS venta_neta,
       SUM(f.iva)                                 AS iva,
       SUM(f.total)                               AS total
  FROM facturas f
 WHERE f.estado = 'emitida'
 GROUP BY 1;

-- Líneas efectivamente vendidas (sólo facturas vigentes)
CREATE OR REPLACE VIEW v_lineas_vendidas AS
SELECT f.id                AS factura_id,
       f.fecha_emision,
       d.producto_id,
       p.sku,
       p.nombre            AS producto,
       c.nombre            AS categoria,
       d.cantidad,
       ROUND(d.cantidad * d.precio_unitario * (1 - d.descuento_pct / 100), 2) AS importe
  FROM facturas f
  JOIN ordenes_venta_detalle d ON d.orden_venta_id = f.orden_venta_id
  JOIN productos p             ON p.id = d.producto_id
  JOIN categorias c            ON c.id = p.categoria_id
 WHERE f.estado = 'emitida';

-- Total de órdenes de compra calculado desde el detalle (no se almacena)
CREATE OR REPLACE VIEW v_ordenes_compra_resumen AS
SELECT oc.id, oc.numero, oc.estado, oc.fecha_emision, oc.fecha_entrega_esperada,
       oc.proveedor_id, pr.razon_social AS proveedor,
       oc.almacen_id,   a.nombre        AS almacen,
       COUNT(d.id)                                       AS num_lineas,
       COALESCE(SUM(d.cantidad * d.costo_unitario), 0)::NUMERIC(14,2) AS total
  FROM ordenes_compra oc
  JOIN proveedores pr ON pr.id = oc.proveedor_id
  JOIN almacenes a    ON a.id = oc.almacen_id
  LEFT JOIN ordenes_compra_detalle d ON d.orden_compra_id = oc.id
 WHERE oc.deleted_at IS NULL
 GROUP BY oc.id, pr.razon_social, a.nombre;

-- Saldo de vacaciones del año en curso
CREATE OR REPLACE VIEW v_saldo_vacaciones AS
SELECT e.id AS empleado_id,
       e.nombres || ' ' || e.apellidos AS empleado,
       e.dias_vacaciones_anuales       AS dias_asignados,
       COALESCE(SUM(s.dias) FILTER (WHERE s.estado = 'aprobada'),  0)::INTEGER AS dias_tomados,
       COALESCE(SUM(s.dias) FILTER (WHERE s.estado = 'pendiente'), 0)::INTEGER AS dias_pendientes,
       (e.dias_vacaciones_anuales
        - COALESCE(SUM(s.dias) FILTER (WHERE s.estado IN ('aprobada','pendiente')), 0))::INTEGER AS dias_disponibles
  FROM empleados e
  LEFT JOIN solicitudes s
         ON s.empleado_id = e.id
        AND s.tipo = 'vacaciones'
        AND date_part('year', s.fecha_inicio) = date_part('year', CURRENT_DATE)
 WHERE e.deleted_at IS NULL
 GROUP BY e.id;
