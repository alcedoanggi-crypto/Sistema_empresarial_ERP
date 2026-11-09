"""Dashboard, reportes exportables y consulta de auditoría."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import Paginacion, aplicar_filtros, igual, paginar
from app.core.deps import get_usuario_actual, requiere
from app.database import get_db
from app.models import Auditoria, Usuario
from app.services.dashboard import kpis
from app.services.reportes import REPORTES, a_excel, a_pdf

router = APIRouter()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(requiere("dashboard", "ver"))):
    return kpis(db)


# ---- Reportes ----------------------------------------------------------------
@router.get("/reportes")
def catalogo_reportes(usuario: Usuario = Depends(get_usuario_actual)):
    """Sólo los reportes de módulos que el usuario puede ver."""
    return [{"clave": k, "titulo": d, "modulo": m} for k, (m, d, _) in REPORTES.items() if usuario.puede(m, "ver")]


@router.get("/reportes/{clave}")
def exportar(clave: str, formato: str = Query("pdf", pattern="^(pdf|excel)$"),
             desde: date | None = None, hasta: date | None = None,
             db: Session = Depends(get_db), usuario: Usuario = Depends(get_usuario_actual)):
    if clave not in REPORTES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reporte inexistente")
    modulo, _, generar = REPORTES[clave]
    if not usuario.puede(modulo, "ver"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin permiso para este reporte")
    rep = generar(db, desde, hasta)
    if formato == "pdf":
        contenido, tipo, ext = a_pdf(rep), "application/pdf", "pdf"
    else:
        contenido = a_excel(rep)
        tipo, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    return Response(contenido, media_type=tipo,
                    headers={"Content-Disposition": f'attachment; filename="{clave}-{date.today()}.{ext}"'})


# ---- Auditoría -----------------------------------------------------------------
@router.get("/auditoria")
def auditoria(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
              _=Depends(requiere("auditoria", "ver"))):
    stmt = select(Auditoria)
    if p.q:
        stmt = stmt.where(Auditoria.tabla.ilike(f"%{p.q}%"))
    stmt = aplicar_filtros(stmt, request, {
        "accion": lambda v: Auditoria.accion == v,
        "tabla": lambda v: Auditoria.tabla == v,
        "usuario_id": igual(Auditoria.usuario_id),
        "desde": lambda v: Auditoria.fecha >= date.fromisoformat(v),
    })
    pagina = paginar(db, stmt.order_by(Auditoria.id.desc()), p)
    pagina["items"] = [{
        "id": a.id, "fecha": a.fecha, "tabla": a.tabla, "registro_id": a.registro_id, "accion": a.accion,
        "usuario": a.usuario_nombre or "(sistema)", "ip": str(a.ip) if a.ip else None,
        "campos_modificados": a.campos_modificados, "datos_anteriores": a.datos_anteriores,
        "datos_nuevos": a.datos_nuevos,
    } for a in pagina["items"]]
    return pagina
