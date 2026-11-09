-- =====================================================================
--  Funciones y triggers
--
--  ¿Por qué triggers y no sólo lógica en Python?
--  Las reglas que protegen la INTEGRIDAD de los datos deben vivir donde
--  están los datos. Si mañana otro sistema, un script de migración o un
--  DBA con psql toca las tablas, los triggers se siguen cumpliendo:
--    * fn_auditoria          -> ningún cambio queda sin registrar.
--    * fn_aplicar_movimiento -> el stock nunca se desincroniza del kardex.
--    * fn_transicion_estado  -> no se puede "saltar" el flujo de un documento.
--    * fn_inmutable          -> kardex y auditoría no se pueden alterar.
-- =====================================================================

-- ---------------------------------------------------------------------
-- updated_at automático
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------
-- AUDITORÍA genérica
-- El backend ejecuta, al inicio de cada transacción:
--     SELECT set_config('app.usuario_id', '<id>', true),
--            set_config('app.ip', '<ip>', true);
-- (true = sólo vive en la transacción actual, seguro con pool de conexiones).
-- El trigger lee esos valores; si no existen (cambio hecho por psql), queda
-- usuario_id NULL, lo que también es información útil.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_auditoria() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_usuario  INTEGER := NULLIF(current_setting('app.usuario_id', true), '')::INTEGER;
    v_ip       INET    := NULLIF(current_setting('app.ip', true), '')::INET;
    v_old      JSONB;
    v_new      JSONB;
    v_campos   TEXT[];
    v_accion   VARCHAR(10);
    v_id       BIGINT;
BEGIN
    IF TG_OP IN ('UPDATE','DELETE') THEN v_old := to_jsonb(OLD); END IF;
    IF TG_OP IN ('INSERT','UPDATE') THEN v_new := to_jsonb(NEW); END IF;

    IF TG_OP = 'INSERT' THEN
        v_accion := 'CREAR';
    ELSIF TG_OP = 'DELETE' THEN
        v_accion := 'ELIMINAR';
    ELSE
        SELECT array_agg(n.key ORDER BY n.key) INTO v_campos
          FROM jsonb_each(v_new) n
         WHERE n.value IS DISTINCT FROM v_old -> n.key
           AND n.key NOT IN ('updated_at','ultimo_acceso');  -- ruido, no se audita
        IF v_campos IS NULL THEN
            RETURN NEW;               -- UPDATE sin cambios reales: no se audita
        END IF;
        v_accion := CASE
            WHEN v_old ->> 'deleted_at' IS NULL AND v_new ->> 'deleted_at' IS NOT NULL THEN 'ELIMINAR'
            WHEN v_old ->> 'deleted_at' IS NOT NULL AND v_new ->> 'deleted_at' IS NULL THEN 'RESTAURAR'
            ELSE 'MODIFICAR'
        END;
    END IF;

    -- id simple o, en tablas de PK compuesta, la primera columna de la PK
    v_id := COALESCE(v_new ->> 'id', v_old ->> 'id',
                     v_new ->> 'rol_id', v_old ->> 'rol_id')::BIGINT;

    INSERT INTO auditoria (tabla, registro_id, accion, usuario_id, ip,
                           datos_anteriores, datos_nuevos, campos_modificados)
    VALUES (TG_TABLE_NAME, v_id, v_accion, v_usuario, v_ip,
            v_old - 'password_hash', v_new - 'password_hash', v_campos);

    RETURN COALESCE(NEW, OLD);
END $$;

-- ---------------------------------------------------------------------
-- KARDEX -> EXISTENCIAS
-- Cada movimiento ajusta el saldo del producto en su almacén. Si una salida
-- dejaría stock negativo se aborta la transacción completa (la venta entera
-- se revierte, no sólo esa línea).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_aplicar_movimiento() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_saldo INTEGER;
BEGIN
    IF NEW.tipo = 'entrada' THEN
        INSERT INTO existencias (producto_id, almacen_id, cantidad)
        VALUES (NEW.producto_id, NEW.almacen_id, NEW.cantidad)
        ON CONFLICT (producto_id, almacen_id)
        DO UPDATE SET cantidad = existencias.cantidad + EXCLUDED.cantidad,
                      updated_at = now();
    ELSE
        UPDATE existencias
           SET cantidad = cantidad - NEW.cantidad, updated_at = now()
         WHERE producto_id = NEW.producto_id AND almacen_id = NEW.almacen_id
               AND cantidad >= NEW.cantidad
        RETURNING cantidad INTO v_saldo;

        IF NOT FOUND THEN
            SELECT cantidad INTO v_saldo FROM existencias
             WHERE producto_id = NEW.producto_id AND almacen_id = NEW.almacen_id;
            RAISE EXCEPTION 'Stock insuficiente para el producto % en el almacén %: disponible %, solicitado %',
                  NEW.producto_id, NEW.almacen_id, COALESCE(v_saldo, 0), NEW.cantidad
                  USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------
-- Máquina de estados de documentos (defensa en profundidad: la API ya
-- valida, pero la BD garantiza que ningún cliente pueda saltarse el flujo).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_transicion_estado() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_permitidas TEXT[];
BEGIN
    IF NEW.estado = OLD.estado THEN
        RETURN NEW;
    END IF;

    v_permitidas := CASE TG_TABLE_NAME
        WHEN 'ordenes_compra' THEN CASE OLD.estado
            WHEN 'borrador' THEN ARRAY['aprobada','cancelada']
            WHEN 'aprobada' THEN ARRAY['recibida','cancelada']
            ELSE ARRAY[]::TEXT[] END
        WHEN 'ordenes_venta' THEN CASE OLD.estado
            WHEN 'pendiente' THEN ARRAY['facturada','cancelada']
            ELSE ARRAY[]::TEXT[] END
        WHEN 'cotizaciones' THEN CASE OLD.estado
            WHEN 'borrador' THEN ARRAY['enviada','aceptada','rechazada','vencida']
            WHEN 'enviada'  THEN ARRAY['aceptada','rechazada','vencida']
            ELSE ARRAY[]::TEXT[] END
        WHEN 'solicitudes' THEN CASE OLD.estado
            WHEN 'pendiente' THEN ARRAY['aprobada','rechazada','cancelada']
            ELSE ARRAY[]::TEXT[] END
        WHEN 'facturas' THEN CASE OLD.estado
            WHEN 'emitida' THEN ARRAY['anulada']
            ELSE ARRAY[]::TEXT[] END
    END;

    IF NOT (NEW.estado = ANY (v_permitidas)) THEN
        RAISE EXCEPTION 'Transición de estado no permitida en %: % -> %',
              TG_TABLE_NAME, OLD.estado, NEW.estado
              USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------
-- Tablas append-only
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_inmutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es de solo inserción: no se permite %', TG_TABLE_NAME, TG_OP
          USING ERRCODE = 'insufficient_privilege';
END $$;

-- =====================================================================
--  Asignación de triggers
-- =====================================================================
DO $$
DECLARE
    t TEXT;
BEGIN
    -- updated_at
    FOREACH t IN ARRAY ARRAY[
        'roles','permisos','departamentos','puestos','empleados','usuarios',
        'asistencias','solicitudes','categorias','productos','almacenes',
        'proveedores','ordenes_compra','clientes','cotizaciones',
        'ordenes_venta','facturas']
    LOOP
        EXECUTE format('CREATE TRIGGER trg_%1$s_updated_at BEFORE UPDATE ON %1$I
                        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at()', t);
    END LOOP;

    -- auditoría
    FOREACH t IN ARRAY ARRAY[
        'roles','permisos','departamentos','puestos','empleados','usuarios',
        'asistencias','solicitudes','categorias','productos','almacenes',
        'proveedores','ordenes_compra','ordenes_compra_detalle','clientes',
        'cotizaciones','cotizaciones_detalle','ordenes_venta',
        'ordenes_venta_detalle','facturas']
    LOOP
        EXECUTE format('CREATE TRIGGER trg_%1$s_auditoria AFTER INSERT OR UPDATE OR DELETE ON %1$I
                        FOR EACH ROW EXECUTE FUNCTION fn_auditoria()', t);
    END LOOP;

    -- flujo de estados
    FOREACH t IN ARRAY ARRAY['ordenes_compra','ordenes_venta','cotizaciones','solicitudes','facturas']
    LOOP
        EXECUTE format('CREATE TRIGGER trg_%1$s_estado BEFORE UPDATE OF estado ON %1$I
                        FOR EACH ROW EXECUTE FUNCTION fn_transicion_estado()', t);
    END LOOP;
END $$;

CREATE TRIGGER trg_movimientos_aplicar
    AFTER INSERT ON movimientos_inventario
    FOR EACH ROW EXECUTE FUNCTION fn_aplicar_movimiento();

CREATE TRIGGER trg_movimientos_inmutable
    BEFORE UPDATE OR DELETE ON movimientos_inventario
    FOR EACH ROW EXECUTE FUNCTION fn_inmutable();

CREATE TRIGGER trg_auditoria_inmutable
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION fn_inmutable();
