from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.crud import Dependiente, Paginacion, aplicar_filtros, aplicar_orden, booleano, crear_router_crud, \
    igual, obtener_o_404, paginar
from app.core.deps import requiere
from app.database import get_db
from app.models import Almacen, Categoria, Movimiento, Producto, Usuario
from app.schemas.comun import Pagina
from app.schemas.inventario import AlmacenActualizar, AlmacenCrear, AlmacenOut, CategoriaActualizar, \
    CategoriaCrear, CategoriaOut, ExistenciaAlmacenOut, MovimientoCrear, MovimientoOut, ProductoActualizar, \
    ProductoCrear, ProductoOut, StockOut

router = APIRouter()

router.include_router(crear_router_crud(
    modelo=Categoria, modulo="inventario",
    esquema_crear=CategoriaCrear, esquema_actualizar=CategoriaActualizar, esquema_salida=CategoriaOut,
    busqueda=[Categoria.nombre], ordenables={"nombre": Categoria.nombre}, orden_defecto=Categoria.nombre,
    dependientes=[Dependiente(Producto, Producto.categoria_id, "La categoría tiene productos vigentes")],
), prefix="/categorias")

router.include_router(crear_router_crud(
    modelo=Almacen, modulo="inventario",
    esquema_crear=AlmacenCrear, esquema_actualizar=AlmacenActualizar, esquema_salida=AlmacenOut,
    busqueda=[Almacen.nombre, Almacen.codigo], filtros={"activo": booleano(Almacen.activo)},
    ordenables={"codigo": Almacen.codigo, "nombre": Almacen.nombre}, orden_defecto=Almacen.codigo,
), prefix="/almacenes")

router.include_router(crear_router_crud(
    modelo=Producto, modulo="inventario",
    esquema_crear=ProductoCrear, esquema_actualizar=ProductoActualizar, esquema_salida=ProductoOut,
    busqueda=[Producto.nombre, Producto.sku],
    filtros={"categoria_id": igual(Producto.categoria_id), "activo": booleano(Producto.activo)},
    ordenables={"sku": Producto.sku, "nombre": Producto.nombre, "precio_venta": Producto.precio_venta},
    orden_defecto=Producto.nombre,
), prefix="/productos")


@router.get("/productos/{id_}/existencias", response_model=list[ExistenciaAlmacenOut])
def existencias_producto(id_: int, db: Session = Depends(get_db), _=Depends(requiere("inventario", "ver"))):
    obtener_o_404(db, Producto, id_)
    filas = db.execute(text("""
        SELECT a.id AS almacen_id, a.nombre AS almacen, COALESCE(e.cantidad, 0) AS cantidad
          FROM almacenes a
          LEFT JOIN existencias e ON e.almacen_id = a.id AND e.producto_id = :id
         WHERE a.deleted_at IS NULL ORDER BY a.codigo"""), {"id": id_}).mappings()
    return [dict(f) for f in filas]


# ---- Stock consolidado (vista v_stock_productos) ---------------------------
_ORDEN_STOCK = {"sku": "sku", "nombre": "nombre", "stock_total": "stock_total", "valor_inventario": "valor_inventario"}


@router.get("/stock", response_model=Pagina[StockOut])
def stock(p: Paginacion = Depends(), estado: str | None = None, categoria: str | None = None,
          db: Session = Depends(get_db), _=Depends(requiere("inventario", "ver"))):
    condiciones, params = ["TRUE"], {}
    if p.q:
        condiciones.append("(nombre ILIKE :q OR sku ILIKE :q)")
        params["q"] = f"%{p.q}%"
    if estado:
        condiciones.append("estado_stock = :estado")
        params["estado"] = estado
    if categoria:
        condiciones.append("categoria = :categoria")
        params["categoria"] = categoria
    campo = _ORDEN_STOCK.get((p.orden or "").lstrip("-"), "nombre")   # lista blanca: sin inyección SQL
    sentido = "DESC" if (p.orden or "").startswith("-") else "ASC"
    where = " AND ".join(condiciones)

    total = db.execute(text(f"SELECT count(*) FROM v_stock_productos WHERE {where}"), params).scalar()
    filas = db.execute(text(
        f"SELECT * FROM v_stock_productos WHERE {where} ORDER BY {campo} {sentido} LIMIT :lim OFFSET :off"
    ), {**params, "lim": p.page_size, "off": (p.page - 1) * p.page_size}).mappings()
    return {"items": [dict(f) for f in filas], "total": total, "page": p.page, "page_size": p.page_size,
            "pages": max(1, -(-total // p.page_size))}


@router.get("/alertas", response_model=list[StockOut])
def alertas_stock(db: Session = Depends(get_db), _=Depends(requiere("inventario", "ver"))):
    filas = db.execute(text("SELECT * FROM v_stock_critico ORDER BY stock_total - stock_minimo, nombre")).mappings()
    return [dict(f) for f in filas]


# ---- Kardex ----------------------------------------------------------------
@router.get("/movimientos", response_model=Pagina[MovimientoOut])
def movimientos(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                _=Depends(requiere("inventario", "ver"))):
    stmt = select(Movimiento)
    if p.q:
        patron = f"%{p.q}%"
        stmt = stmt.where(Movimiento.producto.has(Producto.nombre.ilike(patron) | Producto.sku.ilike(patron))
                          | Movimiento.documento.ilike(patron))
    stmt = aplicar_filtros(stmt, request, {
        "producto_id": igual(Movimiento.producto_id),
        "almacen_id": igual(Movimiento.almacen_id),
        "tipo": lambda v: Movimiento.tipo == v,
        "origen": lambda v: Movimiento.origen == v,
        "desde": lambda v: Movimiento.created_at >= date.fromisoformat(v),
        "hasta": lambda v: Movimiento.created_at < date.fromordinal(date.fromisoformat(v).toordinal() + 1),
    })
    stmt = aplicar_orden(stmt, p.orden, {"created_at": Movimiento.created_at, "cantidad": Movimiento.cantidad},
                         Movimiento.id.desc())
    return paginar(db, stmt, p)


@router.post("/movimientos", response_model=MovimientoOut, status_code=status.HTTP_201_CREATED)
def ajuste(datos: MovimientoCrear, db: Session = Depends(get_db),
           usuario: Usuario = Depends(requiere("inventario", "crear"))):
    """Ajuste manual. Si es una salida sin stock, el trigger aborta y se responde 422."""
    producto = obtener_o_404(db, Producto, datos.producto_id)
    almacen = obtener_o_404(db, Almacen, datos.almacen_id)
    if not almacen.activo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El almacén está inactivo")
    mov = Movimiento(**datos.model_dump(), origen="ajuste", costo_unitario=producto.precio_costo,
                     usuario_id=usuario.id)
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov
