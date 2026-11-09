"""Traduce errores de PostgreSQL a respuestas HTTP legibles.

Las restricciones (UNIQUE, CHECK, FK, EXCLUDE) y los triggers son la última
línea de defensa; aquí se convierten en mensajes que el frontend puede mostrar.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

MENSAJES_RESTRICCION = {
    "ux_usuarios_email": "Ya existe un usuario con ese correo",
    "ux_usuarios_empleado": "Ese empleado ya tiene un usuario asignado",
    "ux_departamentos_codigo": "Ya existe un departamento con ese código",
    "ux_puestos_nombre": "Ya existe un puesto con ese nombre en el departamento",
    "ux_empleados_codigo": "Ya existe un empleado con ese código",
    "ux_empleados_cedula": "Ya existe un empleado con esa cédula",
    "ux_categorias_nombre": "Ya existe una categoría con ese nombre",
    "ux_productos_sku": "Ya existe un producto con ese SKU",
    "ux_almacenes_codigo": "Ya existe un almacén con ese código",
    "ux_proveedores_ruc": "Ya existe un proveedor con ese RUC",
    "ux_clientes_identificacion": "Ya existe un cliente con esa identificación",
    "uq_asistencias_dia": "El empleado ya tiene asistencia registrada ese día",
    "ex_solicitudes_solape": "Ya existe una solicitud pendiente o aprobada que se cruza con esas fechas",
    "ck_empleados_cedula": "La cédula debe tener 10 dígitos",
    "ck_empleados_mayor": "El empleado debe ser mayor de edad a la fecha de ingreso",
    "ck_empleados_fechas": "La fecha de salida no puede ser anterior a la de ingreso",
    "ck_puestos_salarios": "El salario máximo debe ser mayor o igual al mínimo",
    "ck_productos_sku": "El SKU sólo admite mayúsculas, números y guiones (3-30)",
    "ck_proveedores_ruc": "El RUC debe tener 13 dígitos",
    "ck_clientes_ident": "La identificación no coincide con su tipo (cédula 10 dígitos, RUC 13)",
    "ck_asistencias_horas": "La hora de salida debe ser posterior a la de entrada",
    "ck_solicitudes_fechas": "La fecha fin no puede ser anterior a la fecha inicio",
    "ck_existencias_no_negativa": "Stock insuficiente",
    "ck_permisos_ver": "Para otorgar una acción debe otorgarse también 'ver'",
    "ck_departamentos_codigo": "El código sólo admite mayúsculas, números y guiones (2-10)",
}

ESTADO_POR_CODIGO = {
    "23505": 409,  # unique_violation
    "23503": 409,  # foreign_key_violation
    "23P01": 409,  # exclusion_violation
    "23514": 422,  # check_violation (incluye RAISE de triggers)
    "23502": 422,  # not_null_violation
    "42501": 403,  # insufficient_privilege (tablas inmutables)
}


async def manejar_error_bd(request: Request, exc: DBAPIError) -> JSONResponse:
    orig = getattr(exc, "orig", None)
    codigo = getattr(orig, "pgcode", None)
    diag = getattr(orig, "diag", None)
    restriccion = getattr(diag, "constraint_name", None)
    mensaje_pg = getattr(diag, "message_primary", None) or str(orig)

    if restriccion in MENSAJES_RESTRICCION:
        detalle = MENSAJES_RESTRICCION[restriccion]
    elif codigo == "23503":
        detalle = "El registro está relacionado con otros datos y no puede modificarse/eliminarse"
    elif codigo in ESTADO_POR_CODIGO:
        detalle = mensaje_pg
    else:
        return JSONResponse(status_code=500, content={"detail": "Error interno de base de datos"})

    return JSONResponse(
        status_code=ESTADO_POR_CODIGO.get(codigo, 400),
        content={"detail": detalle, "restriccion": restriccion},
    )
