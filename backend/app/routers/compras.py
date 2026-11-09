from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import Dependiente, Paginacion, aplicar_filtros, aplicar_orden, crear_router_crud, igual, \
    obtener_o_404, paginar
from app.core.deps import requiere
from app.database import get_db
from app.models import Almacen, OrdenCompra, OrdenCompraDetalle, Proveedor, Usuario
from app.schemas.comun import Pagina
from app.schemas.compras import OrdenCompraDetalleOut, OrdenCompraIn, OrdenCompraOut, ProveedorActualizar, \
    ProveedorCrear, ProveedorOut
from app.services.compras import recibir_orden
from app.services.documentos import exigir_estado, productos_vigentes

router = APIRouter()

router.include_router(crear_router_crud(
    modelo=Proveedor, modulo="compras",
    esquema_crear=ProveedorCrear, esquema_actualizar=ProveedorActualizar, esquema_salida=ProveedorOut,
    busqueda=[Proveedor.razon_social, Proveedor.ruc, Proveedor.nombre_contacto],
    ordenables={"razon_social": Proveedor.razon_social, "ruc": Proveedor.ruc},
    orden_defecto=Proveedor.razon_social,
    dependientes=[Dependiente(OrdenCompra, OrdenCompra.proveedor_id, "El proveedor tiene órdenes de compra")],
), prefix="/proveedores")


@router.get("/ordenes", response_model=Pagina[OrdenCompraOut])
def listar_ordenes(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                   _=Depends(requiere("compras", "ver"))):
    stmt = select(OrdenCompra).where(OrdenCompra.deleted_at.is_(None))
    if p.q:
        patron = f"%{p.q}%"
        stmt = stmt.where(OrdenCompra.numero.ilike(patron)
                          | OrdenCompra.proveedor.has(Proveedor.razon_social.ilike(patron)))
    stmt = aplicar_filtros(stmt, request, {
        "estado": lambda v: OrdenCompra.estado == v,
        "proveedor_id": igual(OrdenCompra.proveedor_id),
        "desde": lambda v: OrdenCompra.fecha_emision >= date.fromisoformat(v),
        "hasta": lambda v: OrdenCompra.fecha_emision <= date.fromisoformat(v),
    })
    stmt = aplicar_orden(stmt, p.orden, {"numero": OrdenCompra.numero, "fecha_emision": OrdenCompra.fecha_emision},
                         OrdenCompra.id.desc())
    return paginar(db, stmt, p)


@router.get("/ordenes/{id_}", response_model=OrdenCompraDetalleOut)
def obtener_orden(id_: int, db: Session = Depends(get_db), _=Depends(requiere("compras", "ver"))):
    return obtener_o_404(db, OrdenCompra, id_)


def _aplicar(db: Session, orden: OrdenCompra, datos: OrdenCompraIn) -> None:
    obtener_o_404(db, Proveedor, datos.proveedor_id)
    obtener_o_404(db, Almacen, datos.almacen_id)
    productos_vigentes(db, [d.producto_id for d in datos.detalles])
    orden.proveedor_id = datos.proveedor_id
    orden.almacen_id = datos.almacen_id
    orden.fecha_entrega_esperada = datos.fecha_entrega_esperada
    orden.notas = datos.notas
    orden.detalles.clear()
    db.flush()   # borra las líneas anteriores antes de insertar (evita choque con UNIQUE orden+producto)
    orden.detalles.extend(OrdenCompraDetalle(**d.model_dump()) for d in datos.detalles)


@router.post("/ordenes", response_model=OrdenCompraDetalleOut, status_code=status.HTTP_201_CREATED)
def crear_orden(datos: OrdenCompraIn, db: Session = Depends(get_db),
                usuario: Usuario = Depends(requiere("compras", "crear"))):
    orden = OrdenCompra(creado_por=usuario.id)
    db.add(orden)
    _aplicar(db, orden, datos)
    db.commit()
    db.refresh(orden)
    return orden


@router.put("/ordenes/{id_}", response_model=OrdenCompraDetalleOut)
def actualizar_orden(id_: int, datos: OrdenCompraIn, db: Session = Depends(get_db),
                     _=Depends(requiere("compras", "editar"))):
    orden = obtener_o_404(db, OrdenCompra, id_)
    exigir_estado(orden, "borrador", accion="editar")
    _aplicar(db, orden, datos)
    db.commit()
    db.refresh(orden)
    return orden


@router.post("/ordenes/{id_}/aprobar", response_model=OrdenCompraDetalleOut)
def aprobar_orden(id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere("compras", "aprobar"))):
    orden = obtener_o_404(db, OrdenCompra, id_)
    exigir_estado(orden, "borrador", accion="aprobar")
    orden.estado = "aprobada"
    orden.aprobado_por = usuario.id
    orden.fecha_aprobacion = datetime.now(timezone.utc)
    db.commit()
    db.refresh(orden)
    return orden


@router.post("/ordenes/{id_}/recibir", response_model=OrdenCompraDetalleOut)
def recibir(id_: int, db: Session = Depends(get_db), usuario: Usuario = Depends(requiere("compras", "editar"))):
    return recibir_orden(db, id_, usuario)


@router.post("/ordenes/{id_}/cancelar", response_model=OrdenCompraDetalleOut)
def cancelar_orden(id_: int, db: Session = Depends(get_db), _=Depends(requiere("compras", "editar"))):
    orden = obtener_o_404(db, OrdenCompra, id_)
    exigir_estado(orden, "borrador", "aprobada", accion="cancelar")
    orden.estado = "cancelada"
    db.commit()
    db.refresh(orden)
    return orden


@router.delete("/ordenes/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_orden(id_: int, db: Session = Depends(get_db), _=Depends(requiere("compras", "eliminar"))):
    orden = obtener_o_404(db, OrdenCompra, id_)
    exigir_estado(orden, "borrador", accion="eliminar")
    orden.deleted_at = datetime.now(timezone.utc)
    db.commit()
