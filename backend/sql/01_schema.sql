-- =====================================================================
--  Sistema de Administración Empresarial — Esquema (PostgreSQL 15+)
--  Modelo normalizado en 3FN. Convenciones:
--    * PK surrogate "id" (identity) en todas las entidades.
--    * created_at / updated_at en todas las tablas mutables
--      (updated_at lo mantiene el trigger fn_set_updated_at).
--    * Borrado lógico: columna deleted_at (NULL = vigente). Las claves
--      naturales usan índices UNIQUE PARCIALES (WHERE deleted_at IS NULL)
--      para que un registro eliminado no bloquee volver a usar su código.
--    * Montos en NUMERIC(14,2): nunca FLOAT para dinero.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- búsquedas ILIKE '%texto%' con índice
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- restricción EXCLUDE de solicitudes

-- ---------------------------------------------------------------------
-- 1. SEGURIDAD: roles, módulos, permisos, usuarios
-- ---------------------------------------------------------------------
CREATE TABLE roles (
    id           SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre       VARCHAR(30)  NOT NULL UNIQUE,
    descripcion  VARCHAR(200),
    es_sistema   BOOLEAN      NOT NULL DEFAULT FALSE,  -- no se puede eliminar
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_roles_nombre CHECK (nombre ~ '^[a-z_]{3,30}$')
);

CREATE TABLE modulos (
    id      SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave   VARCHAR(30)  NOT NULL UNIQUE,
    nombre  VARCHAR(60)  NOT NULL,
    orden   SMALLINT     NOT NULL DEFAULT 0
);

-- Matriz rol x módulo con acciones granulares (permisos configurables)
CREATE TABLE permisos (
    rol_id          SMALLINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    modulo_id       SMALLINT NOT NULL REFERENCES modulos(id) ON DELETE CASCADE,
    puede_ver       BOOLEAN  NOT NULL DEFAULT FALSE,
    puede_crear     BOOLEAN  NOT NULL DEFAULT FALSE,
    puede_editar    BOOLEAN  NOT NULL DEFAULT FALSE,
    puede_eliminar  BOOLEAN  NOT NULL DEFAULT FALSE,
    puede_aprobar   BOOLEAN  NOT NULL DEFAULT FALSE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (rol_id, modulo_id),
    -- Ninguna acción tiene sentido sin poder ver el módulo
    CONSTRAINT ck_permisos_ver CHECK (
        puede_ver OR NOT (puede_crear OR puede_editar OR puede_eliminar OR puede_aprobar)
    )
);

-- ---------------------------------------------------------------------
-- 2. RECURSOS HUMANOS
-- ---------------------------------------------------------------------
CREATE TABLE departamentos (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo       VARCHAR(10)  NOT NULL,
    nombre       VARCHAR(80)  NOT NULL,
    descripcion  VARCHAR(250),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ,
    CONSTRAINT ck_departamentos_codigo CHECK (codigo ~ '^[A-Z0-9-]{2,10}$')
);
CREATE UNIQUE INDEX ux_departamentos_codigo ON departamentos (codigo) WHERE deleted_at IS NULL;

CREATE TABLE puestos (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    departamento_id  INTEGER       NOT NULL REFERENCES departamentos(id),
    nombre           VARCHAR(80)   NOT NULL,
    salario_min      NUMERIC(12,2) NOT NULL,
    salario_max      NUMERIC(12,2) NOT NULL,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ,
    CONSTRAINT ck_puestos_salarios CHECK (salario_min > 0 AND salario_max >= salario_min)
);
CREATE UNIQUE INDEX ux_puestos_nombre ON puestos (departamento_id, lower(nombre)) WHERE deleted_at IS NULL;
CREATE INDEX ix_puestos_departamento ON puestos (departamento_id);

-- El departamento del empleado se obtiene vía puesto (evita dependencia
-- transitiva empleado -> departamento, requisito de 3FN).
CREATE TABLE empleados (
    id                       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo                   VARCHAR(12)   NOT NULL,
    cedula                   CHAR(10)      NOT NULL,
    nombres                  VARCHAR(80)   NOT NULL,
    apellidos                VARCHAR(80)   NOT NULL,
    email                    VARCHAR(120)  NOT NULL,
    telefono                 VARCHAR(20),
    direccion                VARCHAR(200),
    fecha_nacimiento         DATE          NOT NULL,
    fecha_ingreso            DATE          NOT NULL,
    fecha_salida             DATE,
    puesto_id                INTEGER       NOT NULL REFERENCES puestos(id),
    jefe_id                  INTEGER       REFERENCES empleados(id),
    salario                  NUMERIC(12,2) NOT NULL,
    dias_vacaciones_anuales  SMALLINT      NOT NULL DEFAULT 15,
    estado                   VARCHAR(10)   NOT NULL DEFAULT 'activo',
    created_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ   NOT NULL DEFAULT now(),
    deleted_at               TIMESTAMPTZ,
    CONSTRAINT ck_empleados_cedula   CHECK (cedula ~ '^[0-9]{10}$'),
    CONSTRAINT ck_empleados_email    CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT ck_empleados_salario  CHECK (salario > 0),
    CONSTRAINT ck_empleados_estado   CHECK (estado IN ('activo','licencia','inactivo')),
    CONSTRAINT ck_empleados_vacac    CHECK (dias_vacaciones_anuales BETWEEN 0 AND 60),
    CONSTRAINT ck_empleados_fechas   CHECK (fecha_salida IS NULL OR fecha_salida >= fecha_ingreso),
    CONSTRAINT ck_empleados_mayor    CHECK (fecha_ingreso >= fecha_nacimiento + INTERVAL '18 years'),
    CONSTRAINT ck_empleados_jefe     CHECK (jefe_id IS NULL OR jefe_id <> id)
);
CREATE UNIQUE INDEX ux_empleados_codigo ON empleados (codigo) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_empleados_cedula ON empleados (cedula) WHERE deleted_at IS NULL;
CREATE INDEX ix_empleados_puesto ON empleados (puesto_id);
CREATE INDEX ix_empleados_jefe   ON empleados (jefe_id);
CREATE INDEX ix_empleados_nombre_trgm ON empleados USING gin ((nombres || ' ' || apellidos) gin_trgm_ops);

CREATE TABLE usuarios (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre         VARCHAR(120) NOT NULL,
    email          VARCHAR(120) NOT NULL,
    password_hash  VARCHAR(200) NOT NULL,
    rol_id         SMALLINT     NOT NULL REFERENCES roles(id),
    empleado_id    INTEGER      REFERENCES empleados(id),
    activo         BOOLEAN      NOT NULL DEFAULT TRUE,
    ultimo_acceso  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ,
    CONSTRAINT ck_usuarios_email CHECK (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
CREATE UNIQUE INDEX ux_usuarios_email    ON usuarios (lower(email)) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX ux_usuarios_empleado ON usuarios (empleado_id) WHERE deleted_at IS NULL AND empleado_id IS NOT NULL;
CREATE INDEX ix_usuarios_rol ON usuarios (rol_id);

CREATE TABLE asistencias (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    empleado_id   INTEGER     NOT NULL REFERENCES empleados(id),
    fecha         DATE        NOT NULL,
    hora_entrada  TIME        NOT NULL,
    hora_salida   TIME,
    observacion   VARCHAR(200),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_asistencias_dia UNIQUE (empleado_id, fecha),
    CONSTRAINT ck_asistencias_horas CHECK (hora_salida IS NULL OR hora_salida > hora_entrada)
);
CREATE INDEX ix_asistencias_fecha ON asistencias (fecha);

CREATE TABLE solicitudes (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    empleado_id          INTEGER     NOT NULL REFERENCES empleados(id),
    tipo                 VARCHAR(20) NOT NULL,
    fecha_inicio         DATE        NOT NULL,
    fecha_fin            DATE        NOT NULL,
    dias                 SMALLINT    NOT NULL,
    motivo               VARCHAR(300) NOT NULL,
    estado               VARCHAR(10) NOT NULL DEFAULT 'pendiente',
    revisado_por         INTEGER     REFERENCES usuarios(id),
    fecha_revision       TIMESTAMPTZ,
    comentario_revision  VARCHAR(300),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_solicitudes_tipo   CHECK (tipo IN ('vacaciones','permiso','licencia_medica','otro')),
    CONSTRAINT ck_solicitudes_estado CHECK (estado IN ('pendiente','aprobada','rechazada','cancelada')),
    CONSTRAINT ck_solicitudes_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_solicitudes_dias   CHECK (dias > 0),
    CONSTRAINT ck_solicitudes_revision CHECK (
        estado NOT IN ('aprobada','rechazada') OR (revisado_por IS NOT NULL AND fecha_revision IS NOT NULL)
    ),
    -- Un empleado no puede tener dos solicitudes vigentes que se solapen en fechas
    CONSTRAINT ex_solicitudes_solape EXCLUDE USING gist (
        empleado_id WITH =,
        daterange(fecha_inicio, fecha_fin, '[]') WITH &&
    ) WHERE (estado IN ('pendiente','aprobada'))
);
CREATE INDEX ix_solicitudes_estado ON solicitudes (estado, created_at DESC);

-- ---------------------------------------------------------------------
-- 3. INVENTARIO
-- ---------------------------------------------------------------------
CREATE TABLE categorias (
    id           INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre       VARCHAR(80)  NOT NULL,
    descripcion  VARCHAR(250),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at   TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_categorias_nombre ON categorias (lower(nombre)) WHERE deleted_at IS NULL;

CREATE TABLE productos (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku            VARCHAR(30)   NOT NULL,
    nombre         VARCHAR(120)  NOT NULL,
    descripcion    VARCHAR(500),
    categoria_id   INTEGER       NOT NULL REFERENCES categorias(id),
    unidad_medida  VARCHAR(10)   NOT NULL DEFAULT 'UND',
    precio_costo   NUMERIC(12,2) NOT NULL,
    precio_venta   NUMERIC(12,2) NOT NULL,
    aplica_iva     BOOLEAN       NOT NULL DEFAULT TRUE,
    stock_minimo   INTEGER       NOT NULL DEFAULT 0,
    activo         BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ,
    CONSTRAINT ck_productos_sku     CHECK (sku ~ '^[A-Z0-9-]{3,30}$'),
    CONSTRAINT ck_productos_unidad  CHECK (unidad_medida IN ('UND','KG','LT','MT','CAJA','PAQ')),
    CONSTRAINT ck_productos_precios CHECK (precio_costo >= 0 AND precio_venta >= 0),
    CONSTRAINT ck_productos_minimo  CHECK (stock_minimo >= 0)
);
CREATE UNIQUE INDEX ux_productos_sku ON productos (sku) WHERE deleted_at IS NULL;
CREATE INDEX ix_productos_categoria ON productos (categoria_id);
CREATE INDEX ix_productos_nombre_trgm ON productos USING gin (nombre gin_trgm_ops);

CREATE TABLE almacenes (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo     VARCHAR(10)  NOT NULL,
    nombre     VARCHAR(80)  NOT NULL,
    direccion  VARCHAR(200),
    activo     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX ux_almacenes_codigo ON almacenes (codigo) WHERE deleted_at IS NULL;

-- Saldo actual por producto/almacén. Es un agregado de movimientos_inventario
-- mantenido EXCLUSIVAMENTE por el trigger fn_aplicar_movimiento; se guarda
-- materializado para poder bloquear la fila (SELECT ... FOR UPDATE) al vender.
CREATE TABLE existencias (
    producto_id  INTEGER     NOT NULL REFERENCES productos(id),
    almacen_id   INTEGER     NOT NULL REFERENCES almacenes(id),
    cantidad     INTEGER     NOT NULL DEFAULT 0,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (producto_id, almacen_id),
    CONSTRAINT ck_existencias_no_negativa CHECK (cantidad >= 0)
);
CREATE INDEX ix_existencias_almacen ON existencias (almacen_id);

-- Kardex inmutable (no se actualiza ni se borra; ver trigger fn_inmutable)
CREATE TABLE movimientos_inventario (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id     INTEGER       NOT NULL REFERENCES productos(id),
    almacen_id      INTEGER       NOT NULL REFERENCES almacenes(id),
    tipo            VARCHAR(7)    NOT NULL,
    origen          VARCHAR(10)   NOT NULL,
    cantidad        INTEGER       NOT NULL,
    costo_unitario  NUMERIC(12,2),
    documento       VARCHAR(30),   -- número del documento que lo originó (OC, factura...)
    nota            VARCHAR(250),
    usuario_id      INTEGER       REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT ck_mov_tipo     CHECK (tipo IN ('entrada','salida')),
    CONSTRAINT ck_mov_origen   CHECK (origen IN ('inicial','compra','venta','ajuste','anulacion')),
    CONSTRAINT ck_mov_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_mov_costo    CHECK (costo_unitario IS NULL OR costo_unitario >= 0)
);
CREATE INDEX ix_mov_producto_fecha ON movimientos_inventario (producto_id, created_at DESC);
CREATE INDEX ix_mov_almacen        ON movimientos_inventario (almacen_id);
CREATE INDEX ix_mov_fecha          ON movimientos_inventario (created_at DESC);

-- ---------------------------------------------------------------------
-- 4. COMPRAS
-- ---------------------------------------------------------------------
CREATE TABLE proveedores (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ruc              CHAR(13)     NOT NULL,
    razon_social     VARCHAR(150) NOT NULL,
    nombre_contacto  VARCHAR(100),
    email            VARCHAR(120),
    telefono         VARCHAR(20),
    direccion        VARCHAR(200),
    dias_credito     SMALLINT     NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at       TIMESTAMPTZ,
    CONSTRAINT ck_proveedores_ruc    CHECK (ruc ~ '^[0-9]{13}$'),
    CONSTRAINT ck_proveedores_email  CHECK (email IS NULL OR email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT ck_proveedores_credito CHECK (dias_credito BETWEEN 0 AND 180)
);
CREATE UNIQUE INDEX ux_proveedores_ruc ON proveedores (ruc) WHERE deleted_at IS NULL;
CREATE INDEX ix_proveedores_razon_trgm ON proveedores USING gin (razon_social gin_trgm_ops);

CREATE SEQUENCE seq_orden_compra;

CREATE TABLE ordenes_compra (
    id                      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero                  VARCHAR(20) NOT NULL UNIQUE
                            DEFAULT 'OC-' || lpad(nextval('seq_orden_compra')::text, 6, '0'),
    proveedor_id            INTEGER     NOT NULL REFERENCES proveedores(id),
    almacen_id              INTEGER     NOT NULL REFERENCES almacenes(id),
    estado                  VARCHAR(10) NOT NULL DEFAULT 'borrador',
    fecha_emision           DATE        NOT NULL DEFAULT CURRENT_DATE,
    fecha_entrega_esperada  DATE,
    notas                   VARCHAR(500),
    creado_por              INTEGER     NOT NULL REFERENCES usuarios(id),
    aprobado_por            INTEGER     REFERENCES usuarios(id),
    fecha_aprobacion        TIMESTAMPTZ,
    recibido_por            INTEGER     REFERENCES usuarios(id),
    fecha_recepcion         TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at              TIMESTAMPTZ,
    CONSTRAINT ck_oc_estado CHECK (estado IN ('borrador','aprobada','recibida','cancelada')),
    CONSTRAINT ck_oc_entrega CHECK (fecha_entrega_esperada IS NULL OR fecha_entrega_esperada >= fecha_emision),
    CONSTRAINT ck_oc_aprobacion CHECK (estado NOT IN ('aprobada','recibida') OR aprobado_por IS NOT NULL),
    CONSTRAINT ck_oc_recepcion  CHECK (estado <> 'recibida' OR recibido_por IS NOT NULL)
);
CREATE INDEX ix_oc_proveedor ON ordenes_compra (proveedor_id);
CREATE INDEX ix_oc_estado    ON ordenes_compra (estado, fecha_emision DESC);

CREATE TABLE ordenes_compra_detalle (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_compra_id  INTEGER       NOT NULL REFERENCES ordenes_compra(id) ON DELETE CASCADE,
    producto_id      INTEGER       NOT NULL REFERENCES productos(id),
    cantidad         INTEGER       NOT NULL,
    costo_unitario   NUMERIC(12,2) NOT NULL,
    CONSTRAINT uq_ocd_producto UNIQUE (orden_compra_id, producto_id),
    CONSTRAINT ck_ocd_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_ocd_costo    CHECK (costo_unitario >= 0)
);
CREATE INDEX ix_ocd_producto ON ordenes_compra_detalle (producto_id);

-- ---------------------------------------------------------------------
-- 5. VENTAS
-- ---------------------------------------------------------------------
CREATE TABLE clientes (
    id                   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_identificacion  VARCHAR(10)  NOT NULL,
    identificacion       VARCHAR(13)  NOT NULL,
    nombre               VARCHAR(150) NOT NULL,
    email                VARCHAR(120),
    telefono             VARCHAR(20),
    direccion            VARCHAR(200),
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT now(),
    deleted_at           TIMESTAMPTZ,
    CONSTRAINT ck_clientes_tipo CHECK (tipo_identificacion IN ('cedula','ruc','pasaporte')),
    CONSTRAINT ck_clientes_ident CHECK (
        (tipo_identificacion = 'cedula'    AND identificacion ~ '^[0-9]{10}$') OR
        (tipo_identificacion = 'ruc'       AND identificacion ~ '^[0-9]{13}$') OR
        (tipo_identificacion = 'pasaporte' AND identificacion ~ '^[A-Z0-9]{5,13}$')
    ),
    CONSTRAINT ck_clientes_email CHECK (email IS NULL OR email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
CREATE UNIQUE INDEX ux_clientes_identificacion ON clientes (identificacion) WHERE deleted_at IS NULL;
CREATE INDEX ix_clientes_nombre_trgm ON clientes USING gin (nombre gin_trgm_ops);

CREATE SEQUENCE seq_cotizacion;
CREATE SEQUENCE seq_orden_venta;
CREATE SEQUENCE seq_factura;

CREATE TABLE cotizaciones (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero          VARCHAR(20) NOT NULL UNIQUE
                    DEFAULT 'COT-' || lpad(nextval('seq_cotizacion')::text, 6, '0'),
    cliente_id      INTEGER     NOT NULL REFERENCES clientes(id),
    fecha_emision   DATE        NOT NULL DEFAULT CURRENT_DATE,
    fecha_validez   DATE        NOT NULL,
    estado          VARCHAR(10) NOT NULL DEFAULT 'borrador',
    notas           VARCHAR(500),
    creado_por      INTEGER     NOT NULL REFERENCES usuarios(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT ck_cot_estado CHECK (estado IN ('borrador','enviada','aceptada','rechazada','vencida')),
    CONSTRAINT ck_cot_validez CHECK (fecha_validez >= fecha_emision)
);
CREATE INDEX ix_cot_cliente ON cotizaciones (cliente_id);

-- precio_unitario es una "foto" del precio al momento del documento: depende
-- de la línea del documento, no del producto, por lo que no viola 3FN.
CREATE TABLE cotizaciones_detalle (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cotizacion_id    INTEGER       NOT NULL REFERENCES cotizaciones(id) ON DELETE CASCADE,
    producto_id      INTEGER       NOT NULL REFERENCES productos(id),
    cantidad         INTEGER       NOT NULL,
    precio_unitario  NUMERIC(12,2) NOT NULL,
    descuento_pct    NUMERIC(5,2)  NOT NULL DEFAULT 0,
    CONSTRAINT uq_cotd_producto UNIQUE (cotizacion_id, producto_id),
    CONSTRAINT ck_cotd_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_cotd_precio   CHECK (precio_unitario >= 0),
    CONSTRAINT ck_cotd_desc     CHECK (descuento_pct BETWEEN 0 AND 100)
);

CREATE TABLE ordenes_venta (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero         VARCHAR(20) NOT NULL UNIQUE
                   DEFAULT 'OV-' || lpad(nextval('seq_orden_venta')::text, 6, '0'),
    cliente_id     INTEGER     NOT NULL REFERENCES clientes(id),
    cotizacion_id  INTEGER     UNIQUE REFERENCES cotizaciones(id),
    almacen_id     INTEGER     NOT NULL REFERENCES almacenes(id),
    estado         VARCHAR(10) NOT NULL DEFAULT 'pendiente',
    fecha          DATE        NOT NULL DEFAULT CURRENT_DATE,
    notas          VARCHAR(500),
    creado_por     INTEGER     NOT NULL REFERENCES usuarios(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ,
    CONSTRAINT ck_ov_estado CHECK (estado IN ('pendiente','facturada','cancelada'))
);
CREATE INDEX ix_ov_cliente ON ordenes_venta (cliente_id);
CREATE INDEX ix_ov_estado  ON ordenes_venta (estado, fecha DESC);

CREATE TABLE ordenes_venta_detalle (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_venta_id   INTEGER       NOT NULL REFERENCES ordenes_venta(id) ON DELETE CASCADE,
    producto_id      INTEGER       NOT NULL REFERENCES productos(id),
    cantidad         INTEGER       NOT NULL,
    precio_unitario  NUMERIC(12,2) NOT NULL,
    descuento_pct    NUMERIC(5,2)  NOT NULL DEFAULT 0,
    CONSTRAINT uq_ovd_producto UNIQUE (orden_venta_id, producto_id),
    CONSTRAINT ck_ovd_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_ovd_precio   CHECK (precio_unitario >= 0),
    CONSTRAINT ck_ovd_desc     CHECK (descuento_pct BETWEEN 0 AND 100)
);
CREATE INDEX ix_ovd_producto ON ordenes_venta_detalle (producto_id);

-- Los totales de la factura se guardan (desnormalización deliberada): una
-- factura es un documento fiscal inmutable; si mañana cambia la tasa de IVA
-- o se corrige un precio, la factura emitida NO debe recalcularse.
CREATE TABLE facturas (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero            VARCHAR(20)   NOT NULL UNIQUE
                      DEFAULT '001-001-' || lpad(nextval('seq_factura')::text, 9, '0'),
    orden_venta_id    INTEGER       NOT NULL UNIQUE REFERENCES ordenes_venta(id),
    fecha_emision     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    subtotal          NUMERIC(14,2) NOT NULL,
    descuento         NUMERIC(14,2) NOT NULL DEFAULT 0,
    iva               NUMERIC(14,2) NOT NULL,
    total             NUMERIC(14,2) NOT NULL,
    tasa_iva          NUMERIC(5,2)  NOT NULL,
    estado            VARCHAR(10)   NOT NULL DEFAULT 'emitida',
    emitida_por       INTEGER       NOT NULL REFERENCES usuarios(id),
    anulada_por       INTEGER       REFERENCES usuarios(id),
    fecha_anulacion   TIMESTAMPTZ,
    motivo_anulacion  VARCHAR(300),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT ck_fac_estado  CHECK (estado IN ('emitida','anulada')),
    CONSTRAINT ck_fac_montos  CHECK (subtotal >= 0 AND descuento >= 0 AND iva >= 0 AND descuento <= subtotal),
    CONSTRAINT ck_fac_total   CHECK (total = subtotal - descuento + iva),
    CONSTRAINT ck_fac_anulada CHECK (estado <> 'anulada' OR (anulada_por IS NOT NULL AND motivo_anulacion IS NOT NULL))
);
CREATE INDEX ix_fac_fecha ON facturas (fecha_emision DESC) WHERE estado = 'emitida';

-- ---------------------------------------------------------------------
-- 6. AUDITORÍA (la llenan triggers; ver 02_funciones_triggers.sql)
-- ---------------------------------------------------------------------
CREATE TABLE auditoria (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tabla               VARCHAR(60) NOT NULL,
    registro_id         BIGINT,
    accion              VARCHAR(10) NOT NULL,
    usuario_id          INTEGER     REFERENCES usuarios(id),
    ip                  INET,
    datos_anteriores    JSONB,
    datos_nuevos        JSONB,
    campos_modificados  TEXT[],
    fecha               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_auditoria_accion CHECK (accion IN ('CREAR','MODIFICAR','ELIMINAR','RESTAURAR'))
);
CREATE INDEX ix_auditoria_registro ON auditoria (tabla, registro_id);
CREATE INDEX ix_auditoria_usuario  ON auditoria (usuario_id);
CREATE INDEX ix_auditoria_fecha    ON auditoria (fecha DESC);
