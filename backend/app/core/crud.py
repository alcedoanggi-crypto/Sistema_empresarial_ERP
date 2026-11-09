"""Paginación, búsqueda, filtros y un generador de CRUD con borrado lógico.

Los catálogos simples (departamentos, categorías, proveedores...) comparten el
mismo comportamiento; en vez de repetir 5 endpoints por entidad se generan con
crear_router_crud(). Los documentos con reglas de negocio (órdenes, facturas)
tienen routers propios.
"""
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import requiere
from app.database import get_db
from app.schemas.comun import Pagina


@dataclass
class Paginacion:
    page: int = Query(1, ge=1)
    page_size: int = Query(10, ge=1, le=500)
    q: str | None = Query(None, description="Texto de búsqueda")
    orden: str | None = Query(None, description="Campo de orden; prefijo '-' para descendente")


def aplicar_busqueda(stmt: Select, q: str | None, columnas: list) -> Select:
    if q and columnas:
        patron = f"%{q.strip()}%"
        stmt = stmt.where(or_(*[c.ilike(patron) for c in columnas]))
    return stmt


def aplicar_filtros(stmt: Select, request: Request, filtros: dict[str, Callable[[str], Any]]) -> Select:
    for nombre, condicion in filtros.items():
        valor = request.query_params.get(nombre)
        if valor not in (None, ""):
            try:
                stmt = stmt.where(condicion(valor))
            except ValueError:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Valor inválido para '{nombre}'")
    return stmt


def aplicar_orden(stmt: Select, orden: str | None, ordenables: dict[str, Any], defecto) -> Select:
    if orden:
        desc = orden.startswith("-")
        columna = ordenables.get(orden.lstrip("-"))
        if columna is not None:
            return stmt.order_by(columna.desc() if desc else columna.asc())
    return stmt.order_by(*defecto) if isinstance(defecto, (list, tuple)) else stmt.order_by(defecto)


def paginar(db: Session, stmt: Select, p: Paginacion, escalares: bool = True) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    resultado = db.execute(stmt.limit(p.page_size).offset((p.page - 1) * p.page_size))
    items = resultado.scalars().all() if escalares else [dict(r) for r in resultado.mappings()]
    return {
        "items": items,
        "total": total,
        "page": p.page,
        "page_size": p.page_size,
        "pages": max(1, math.ceil(total / p.page_size)),
    }


def obtener_o_404(db: Session, modelo, id_: int, incluir_eliminados: bool = False):
    obj = db.get(modelo, id_)
    if obj is None or (not incluir_eliminados and getattr(obj, "deleted_at", None) is not None):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{modelo.__name__} {id_} no encontrado")
    return obj


def igual(columna, tipo=int):
    return lambda v: columna == tipo(v)


def booleano(columna):
    return lambda v: columna.is_(v.lower() in ("1", "true", "si", "sí"))


@dataclass
class Dependiente:
    """Hijos vigentes que impiden el borrado lógico del padre."""
    modelo: Any
    fk: Any
    mensaje: str


def crear_router_crud(
    *,
    modelo,
    modulo: str,
    esquema_crear: type[BaseModel],
    esquema_actualizar: type[BaseModel],
    esquema_salida: type[BaseModel],
    busqueda: list | None = None,
    filtros: dict[str, Callable[[str], Any]] | None = None,
    ordenables: dict[str, Any] | None = None,
    orden_defecto=None,
    dependientes: list[Dependiente] | None = None,
    validar: Callable[[Session, dict, Any | None], None] | None = None,
) -> APIRouter:
    router = APIRouter()
    filtros = filtros or {}
    ordenables = ordenables or {}
    orden_defecto = orden_defecto if orden_defecto is not None else modelo.id.desc()
    dependientes = dependientes or []

    @router.get("", response_model=Pagina[esquema_salida])
    def listar(
        request: Request,
        p: Paginacion = Depends(),
        eliminados: bool = Query(False, description="Listar sólo los eliminados (papelera)"),
        db: Session = Depends(get_db),
        _=Depends(requiere(modulo, "ver")),
    ):
        stmt = select(modelo).where(
            modelo.deleted_at.is_not(None) if eliminados else modelo.deleted_at.is_(None)
        )
        stmt = aplicar_busqueda(stmt, p.q, busqueda or [])
        stmt = aplicar_filtros(stmt, request, filtros)
        stmt = aplicar_orden(stmt, p.orden, ordenables, orden_defecto)
        return paginar(db, stmt, p)

    @router.get("/{id_}", response_model=esquema_salida)
    def obtener(id_: int, db: Session = Depends(get_db), _=Depends(requiere(modulo, "ver"))):
        return obtener_o_404(db, modelo, id_)

    @router.post("", response_model=esquema_salida, status_code=status.HTTP_201_CREATED)
    def crear(datos: esquema_crear, db: Session = Depends(get_db), _=Depends(requiere(modulo, "crear"))):
        valores = datos.model_dump()
        if validar:
            validar(db, valores, None)
        obj = modelo(**valores)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.put("/{id_}", response_model=esquema_salida)
    def actualizar(id_: int, datos: esquema_actualizar, db: Session = Depends(get_db),
                   _=Depends(requiere(modulo, "editar"))):
        obj = obtener_o_404(db, modelo, id_)
        valores = datos.model_dump(exclude_unset=True)
        if validar:
            validar(db, valores, obj)
        for campo, valor in valores.items():
            setattr(obj, campo, valor)
        db.commit()
        db.refresh(obj)
        return obj

    @router.delete("/{id_}", status_code=status.HTTP_204_NO_CONTENT)
    def eliminar(id_: int, db: Session = Depends(get_db), _=Depends(requiere(modulo, "eliminar"))):
        obj = obtener_o_404(db, modelo, id_)
        for dep in dependientes:
            vigentes = db.scalar(
                select(func.count()).select_from(dep.modelo)
                .where(dep.fk == obj.id, dep.modelo.deleted_at.is_(None))
            )
            if vigentes:
                raise HTTPException(status.HTTP_409_CONFLICT, f"{dep.mensaje} ({vigentes})")
        obj.deleted_at = datetime.now(timezone.utc)   # borrado lógico
        db.commit()

    @router.post("/{id_}/restaurar", response_model=esquema_salida)
    def restaurar(id_: int, db: Session = Depends(get_db), _=Depends(requiere(modulo, "eliminar"))):
        obj = obtener_o_404(db, modelo, id_, incluir_eliminados=True)
        obj.deleted_at = None
        db.commit()   # si su código ya fue reutilizado, el índice único parcial lo impide (409)
        db.refresh(obj)
        return obj

    return router
