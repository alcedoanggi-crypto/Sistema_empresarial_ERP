from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import Dependiente, Paginacion, aplicar_filtros, aplicar_orden, crear_router_crud, igual, \
    obtener_o_404, paginar
from app.core.deps import requiere
from app.database import get_db
from app.models import Almacen, Cliente, Cotizacion, CotizacionDetalle, Factura, OrdenVenta, OrdenVentaDetalle, \
    Usuario
from app.schemas.comun import Pagina
from app.schemas.ventas import AnulacionIn, ClienteActualizar, ClienteCrear, ClienteOut, ConvertirCotizacionIn, \
    CotizacionDetalleOut, CotizacionIn, CotizacionOut, FacturaOut, OrdenVentaDetalleOut, OrdenVentaIn, OrdenVentaOut
from app.services.documentos import exigir_estado, lineas_venta
from app.services.reportes import factura_pdf
from app.services.ventas import anular_factura, facturar

router = APIRouter()

router.include_router(crear_router_crud(
    modelo=Cliente, modulo="ventas",
    esquema_crear=ClienteCrear, esquema_actualizar=ClienteActualizar, esquema_salida=ClienteOut,
    busqueda=[Cliente.nombre, Cliente.identificacion, Cliente.email],
    filtros={"tipo_identificacion": lambda v: Cliente.tipo_identificacion == v},
    ordenables={"nombre": Cliente.nombre, "identificacion": Cliente.identificacion},
    orden_defecto=Cliente.nombre,
    dependientes=[Dependiente(OrdenVenta, OrdenVenta.cliente_id, "El cliente tiene órdenes de venta")],
), prefix="/clientes")


def _filtros_documento(modelo, campo_fecha):
    return {
        "estado": lambda v: modelo.estado == v,
        "cliente_id": igual(modelo.cliente_id),
        "desde": lambda v: campo_fecha >= date.fromisoformat(v),
        "hasta": lambda v: campo_fecha <= date.fromisoformat(v),
    }


def _buscar_documento(stmt, modelo, q: str | None):
    if q:
        patron = f"%{q}%"
        stmt = stmt.where(modelo.numero.ilike(patron) | modelo.cliente.has(Cliente.nombre.ilike(patron)))
    return stmt


# ---- Cotizaciones ----------------------------------------------------------
@router.get("/cotizaciones", response_model=Pagina[CotizacionOut])
def listar_cotizaciones(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                        _=Depends(requiere("ventas", "ver"))):
    stmt = _buscar_documento(select(Cotizacion).where(Cotizacion.deleted_at.is_(None)), Cotizacion, p.q)
    stmt = aplicar_filtros(stmt, request, _filtros_documento(Cotizacion, Cotizacion.fecha_emision))
    stmt = aplicar_orden(stmt, p.orden, {"numero": Cotizacion.numero, "fecha_emision": Cotizacion.fecha_emision},
                         Cotizacion.id.desc())
    return paginar(db, stmt, p)


@router.get("/cotizaciones/{id_}", response_model=CotizacionDetalleOut)
def obtener_cotizacion(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "ver"))):
    return obtener_o_404(db, Cotizacion, id_)


def _aplicar_cotizacion(db: Session, cot: Cotizacion, datos: CotizacionIn) -> None:
    obtener_o_404(db, Cliente, datos.cliente_id)
    cot.cliente_id = datos.cliente_id
    cot.fecha_validez = datos.fecha_validez
    cot.notas = datos.notas
    cot.detalles.clear()
    db.flush()
    cot.detalles.extend(lineas_venta(db, datos.detalles, CotizacionDetalle))


@router.post("/cotizaciones", response_model=CotizacionDetalleOut, status_code=status.HTTP_201_CREATED)
def crear_cotizacion(datos: CotizacionIn, db: Session = Depends(get_db),
                     usuario: Usuario = Depends(requiere("ventas", "crear"))):
    if datos.fecha_validez < date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La fecha de validez ya pasó")
    cot = Cotizacion(creado_por=usuario.id)
    db.add(cot)
    _aplicar_cotizacion(db, cot, datos)
    db.commit()
    db.refresh(cot)
    return cot


@router.put("/cotizaciones/{id_}", response_model=CotizacionDetalleOut)
def actualizar_cotizacion(id_: int, datos: CotizacionIn, db: Session = Depends(get_db),
                          _=Depends(requiere("ventas", "editar"))):
    cot = obtener_o_404(db, Cotizacion, id_)
    exigir_estado(cot, "borrador", accion="editar")
    _aplicar_cotizacion(db, cot, datos)
    db.commit()
    db.refresh(cot)
    return cot


def _cambiar_estado_cotizacion(db: Session, id_: int, destino: str, origenes: tuple[str, ...], accion: str):
    cot = obtener_o_404(db, Cotizacion, id_)
    exigir_estado(cot, *origenes, accion=accion)
    cot.estado = destino
    db.commit()
    db.refresh(cot)
    return cot


@router.post("/cotizaciones/{id_}/enviar", response_model=CotizacionDetalleOut)
def enviar_cotizacion(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "editar"))):
    return _cambiar_estado_cotizacion(db, id_, "enviada", ("borrador",), "enviar")


@router.post("/cotizaciones/{id_}/rechazar", response_model=CotizacionDetalleOut)
def rechazar_cotizacion(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "editar"))):
    return _cambiar_estado_cotizacion(db, id_, "rechazada", ("borrador", "enviada"), "rechazar")


@router.post("/cotizaciones/{id_}/convertir", response_model=OrdenVentaDetalleOut,
             status_code=status.HTTP_201_CREATED)
def convertir_cotizacion(id_: int, datos: ConvertirCotizacionIn, db: Session = Depends(get_db),
                         usuario: Usuario = Depends(requiere("ventas", "crear"))):
    """Cliente acepta: la cotización pasa a 'aceptada' y genera su orden de venta."""
    cot = obtener_o_404(db, Cotizacion, id_)
    exigir_estado(cot, "borrador", "enviada", accion="convertir")
    if cot.fecha_validez < date.today():
        cot.estado = "vencida"
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, f"La cotización venció el {cot.fecha_validez:%d/%m/%Y}")
    obtener_o_404(db, Almacen, datos.almacen_id)

    orden = OrdenVenta(cliente_id=cot.cliente_id, cotizacion_id=cot.id, almacen_id=datos.almacen_id,
                       notas=f"Generada desde {cot.numero}", creado_por=usuario.id)
    orden.detalles = [
        OrdenVentaDetalle(producto_id=d.producto_id, cantidad=d.cantidad, precio_unitario=d.precio_unitario,
                          descuento_pct=d.descuento_pct)
        for d in cot.detalles
    ]
    cot.estado = "aceptada"
    db.add(orden)
    db.commit()
    db.refresh(orden)
    return orden


# ---- Órdenes de venta ------------------------------------------------------
@router.get("/ordenes", response_model=Pagina[OrdenVentaOut])
def listar_ordenes(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                   _=Depends(requiere("ventas", "ver"))):
    stmt = _buscar_documento(select(OrdenVenta).where(OrdenVenta.deleted_at.is_(None)), OrdenVenta, p.q)
    stmt = aplicar_filtros(stmt, request, _filtros_documento(OrdenVenta, OrdenVenta.fecha))
    stmt = aplicar_orden(stmt, p.orden, {"numero": OrdenVenta.numero, "fecha": OrdenVenta.fecha}, OrdenVenta.id.desc())
    return paginar(db, stmt, p)


@router.get("/ordenes/{id_}", response_model=OrdenVentaDetalleOut)
def obtener_orden(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "ver"))):
    return obtener_o_404(db, OrdenVenta, id_)


def _aplicar_orden(db: Session, orden: OrdenVenta, datos: OrdenVentaIn) -> None:
    obtener_o_404(db, Cliente, datos.cliente_id)
    obtener_o_404(db, Almacen, datos.almacen_id)
    orden.cliente_id = datos.cliente_id
    orden.almacen_id = datos.almacen_id
    orden.notas = datos.notas
    orden.detalles.clear()
    db.flush()
    orden.detalles.extend(lineas_venta(db, datos.detalles, OrdenVentaDetalle))


@router.post("/ordenes", response_model=OrdenVentaDetalleOut, status_code=status.HTTP_201_CREATED)
def crear_orden(datos: OrdenVentaIn, db: Session = Depends(get_db),
                usuario: Usuario = Depends(requiere("ventas", "crear"))):
    orden = OrdenVenta(creado_por=usuario.id)
    db.add(orden)
    _aplicar_orden(db, orden, datos)
    db.commit()
    db.refresh(orden)
    return orden


@router.put("/ordenes/{id_}", response_model=OrdenVentaDetalleOut)
def actualizar_orden(id_: int, datos: OrdenVentaIn, db: Session = Depends(get_db),
                     _=Depends(requiere("ventas", "editar"))):
    orden = obtener_o_404(db, OrdenVenta, id_)
    exigir_estado(orden, "pendiente", accion="editar")
    _aplicar_orden(db, orden, datos)
    db.commit()
    db.refresh(orden)
    return orden


@router.post("/ordenes/{id_}/cancelar", response_model=OrdenVentaDetalleOut)
def cancelar_orden(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "editar"))):
    orden = obtener_o_404(db, OrdenVenta, id_)
    exigir_estado(orden, "pendiente", accion="cancelar")
    orden.estado = "cancelada"
    db.commit()
    db.refresh(orden)
    return orden


@router.post("/ordenes/{id_}/facturar", response_model=FacturaOut, status_code=status.HTTP_201_CREATED)
def facturar_orden(id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere("ventas", "crear"))):
    return facturar(db, id_, usuario)


# ---- Facturas --------------------------------------------------------------
@router.get("/facturas", response_model=Pagina[FacturaOut])
def listar_facturas(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                    _=Depends(requiere("ventas", "ver"))):
    stmt = select(Factura).join(Factura.orden_venta).join(OrdenVenta.cliente)
    if p.q:
        patron = f"%{p.q}%"
        stmt = stmt.where(Factura.numero.ilike(patron) | Cliente.nombre.ilike(patron))
    stmt = aplicar_filtros(stmt, request, {
        "estado": lambda v: Factura.estado == v,
        "cliente_id": igual(OrdenVenta.cliente_id),
        "desde": lambda v: Factura.fecha_emision >= date.fromisoformat(v),
        "hasta": lambda v: Factura.fecha_emision < date.fromordinal(date.fromisoformat(v).toordinal() + 1),
    })
    stmt = aplicar_orden(stmt, p.orden, {"numero": Factura.numero, "fecha_emision": Factura.fecha_emision,
                                         "total": Factura.total}, Factura.id.desc())
    return paginar(db, stmt, p)


@router.get("/facturas/{id_}", response_model=FacturaOut)
def obtener_factura(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "ver"))):
    return obtener_o_404(db, Factura, id_)


@router.get("/facturas/{id_}/pdf")
def descargar_factura(id_: int, db: Session = Depends(get_db), _=Depends(requiere("ventas", "ver"))):
    factura = obtener_o_404(db, Factura, id_)
    return Response(factura_pdf(factura), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="factura-{factura.numero}.pdf"'})


@router.post("/facturas/{id_}/anular", response_model=FacturaOut)
def anular(id_: int, datos: AnulacionIn, db: Session = Depends(get_db),
           usuario: Usuario = Depends(requiere("ventas", "aprobar"))):
    return anular_factura(db, id_, datos.motivo, usuario)
