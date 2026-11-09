from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import extract, select, text
from sqlalchemy.orm import Session

from app.core.crud import Dependiente, Paginacion, aplicar_filtros, aplicar_orden, crear_router_crud, igual, \
    obtener_o_404, paginar
from app.core.deps import get_usuario_actual, requiere
from app.database import get_db
from app.models import Asistencia, Departamento, Empleado, Puesto, Solicitud, Usuario
from app.schemas.comun import Pagina
from app.schemas.rrhh import AsistenciaActualizar, AsistenciaCrear, AsistenciaOut, DepartamentoActualizar, \
    DepartamentoCrear, DepartamentoOut, EmpleadoActualizar, EmpleadoCrear, EmpleadoOut, PuestoActualizar, \
    PuestoCrear, PuestoOut, RevisionIn, SaldoVacacionesOut, SolicitudCrear, SolicitudOut
from app.services.rrhh import dias_habiles, saldo_vacaciones, validar_saldo

router = APIRouter()


# ---- Catálogos (CRUD genérico) -------------------------------------------
def _validar_empleado(db: Session, valores: dict, actual: Empleado | None) -> None:
    """El salario debe estar dentro de la banda del puesto."""
    puesto_id = valores.get("puesto_id", actual.puesto_id if actual else None)
    salario = valores.get("salario", actual.salario if actual else None)
    puesto = db.get(Puesto, puesto_id) if puesto_id else None
    if puesto is None or puesto.deleted_at is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Puesto inexistente")
    if salario is not None and not (puesto.salario_min <= salario <= puesto.salario_max):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El salario debe estar entre {puesto.salario_min} y {puesto.salario_max} para el puesto {puesto.nombre}",
        )


router.include_router(crear_router_crud(
    modelo=Departamento, modulo="rrhh",
    esquema_crear=DepartamentoCrear, esquema_actualizar=DepartamentoActualizar, esquema_salida=DepartamentoOut,
    busqueda=[Departamento.nombre, Departamento.codigo],
    ordenables={"codigo": Departamento.codigo, "nombre": Departamento.nombre},
    orden_defecto=Departamento.nombre,
    dependientes=[Dependiente(Puesto, Puesto.departamento_id, "El departamento tiene puestos vigentes")],
), prefix="/departamentos")

router.include_router(crear_router_crud(
    modelo=Puesto, modulo="rrhh",
    esquema_crear=PuestoCrear, esquema_actualizar=PuestoActualizar, esquema_salida=PuestoOut,
    busqueda=[Puesto.nombre],
    filtros={"departamento_id": igual(Puesto.departamento_id)},
    ordenables={"nombre": Puesto.nombre, "salario_min": Puesto.salario_min},
    orden_defecto=Puesto.nombre,
    dependientes=[Dependiente(Empleado, Empleado.puesto_id, "El puesto tiene empleados asignados")],
), prefix="/puestos")

router.include_router(crear_router_crud(
    modelo=Empleado, modulo="rrhh",
    esquema_crear=EmpleadoCrear, esquema_actualizar=EmpleadoActualizar, esquema_salida=EmpleadoOut,
    busqueda=[Empleado.nombres, Empleado.apellidos, Empleado.cedula, Empleado.codigo, Empleado.email],
    filtros={
        "estado": lambda v: Empleado.estado == v,
        "puesto_id": igual(Empleado.puesto_id),
        "departamento_id": lambda v: Empleado.puesto.has(Puesto.departamento_id == int(v)),
    },
    ordenables={"codigo": Empleado.codigo, "apellidos": Empleado.apellidos, "fecha_ingreso": Empleado.fecha_ingreso,
                "salario": Empleado.salario},
    orden_defecto=Empleado.apellidos,
    validar=_validar_empleado,
), prefix="/empleados")


@router.get("/empleados/{id_}/vacaciones", response_model=SaldoVacacionesOut)
def vacaciones_empleado(id_: int, db: Session = Depends(get_db), _=Depends(requiere("rrhh", "ver"))):
    saldo = saldo_vacaciones(db, id_)
    if saldo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Empleado no encontrado")
    return saldo


# ---- Asistencia ----------------------------------------------------------
@router.get("/asistencias", response_model=Pagina[AsistenciaOut])
def listar_asistencias(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                       _=Depends(requiere("rrhh", "ver"))):
    stmt = select(Asistencia)
    if p.q:
        patron = f"%{p.q}%"
        stmt = stmt.where(Asistencia.empleado.has((Empleado.nombres + " " + Empleado.apellidos).ilike(patron)))
    stmt = aplicar_filtros(stmt, request, {
        "empleado_id": igual(Asistencia.empleado_id),
        "desde": lambda v: Asistencia.fecha >= date.fromisoformat(v),
        "hasta": lambda v: Asistencia.fecha <= date.fromisoformat(v),
    })
    stmt = aplicar_orden(stmt, p.orden, {"fecha": Asistencia.fecha, "hora_entrada": Asistencia.hora_entrada},
                         [Asistencia.fecha.desc(), Asistencia.hora_entrada])
    return paginar(db, stmt, p)


@router.post("/asistencias", response_model=AsistenciaOut, status_code=status.HTTP_201_CREATED)
def registrar_asistencia(datos: AsistenciaCrear, db: Session = Depends(get_db),
                         _=Depends(requiere("rrhh", "crear"))):
    asistencia = Asistencia(**datos.model_dump())
    db.add(asistencia)
    db.commit()
    db.refresh(asistencia)
    return asistencia


@router.put("/asistencias/{id_}", response_model=AsistenciaOut)
def corregir_asistencia(id_: int, datos: AsistenciaActualizar, db: Session = Depends(get_db),
                        _=Depends(requiere("rrhh", "editar"))):
    asistencia = obtener_o_404(db, Asistencia, id_)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(asistencia, campo, valor)
    db.commit()
    db.refresh(asistencia)
    return asistencia


@router.get("/asistencias/resumen")
def resumen_asistencia(anio: int = Query(...), mes: int = Query(..., ge=1, le=12), db: Session = Depends(get_db),
                       _=Depends(requiere("rrhh", "ver"))):
    """Días trabajados, atrasos y horas por empleado en un mes."""
    filas = db.execute(text("""
        SELECT e.id AS empleado_id, e.nombres || ' ' || e.apellidos AS empleado,
               count(a.id)::int AS dias_trabajados,
               count(a.id) FILTER (WHERE a.hora_entrada > TIME '08:15')::int AS atrasos,
               round(COALESCE(sum(EXTRACT(EPOCH FROM (a.hora_salida - a.hora_entrada)) / 3600), 0)::numeric, 1)::float
                   AS horas
          FROM empleados e
          LEFT JOIN asistencias a ON a.empleado_id = e.id
               AND EXTRACT(YEAR FROM a.fecha) = :anio AND EXTRACT(MONTH FROM a.fecha) = :mes
         WHERE e.deleted_at IS NULL AND e.estado <> 'inactivo'
         GROUP BY e.id ORDER BY e.apellidos"""), {"anio": anio, "mes": mes}).mappings()
    return [dict(f) for f in filas]


# ---- Autoservicio del empleado --------------------------------------------
def _empleado_de(usuario: Usuario) -> Empleado:
    if usuario.empleado is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Su usuario no está vinculado a un empleado")
    return usuario.empleado


@router.get("/mi-asistencia", response_model=list[AsistenciaOut])
def mi_asistencia(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere("autoservicio", "ver"))):
    empleado = _empleado_de(usuario)
    hoy = date.today()
    return db.scalars(
        select(Asistencia).where(Asistencia.empleado_id == empleado.id,
                                 extract("year", Asistencia.fecha) == hoy.year,
                                 extract("month", Asistencia.fecha) == hoy.month)
        .order_by(Asistencia.fecha.desc())
    ).all()


@router.post("/mi-asistencia/marcar", response_model=AsistenciaOut)
def marcar(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere("autoservicio", "crear"))):
    """Primera marca del día = entrada; segunda = salida."""
    empleado = _empleado_de(usuario)
    ahora = datetime.now().time().replace(microsecond=0)
    registro = db.scalar(select(Asistencia).where(Asistencia.empleado_id == empleado.id,
                                                   Asistencia.fecha == date.today()))
    if registro is None:
        registro = Asistencia(empleado_id=empleado.id, fecha=date.today(), hora_entrada=ahora)
        db.add(registro)
    elif registro.hora_salida is None:
        registro.hora_salida = ahora
    else:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya registró entrada y salida hoy")
    db.commit()
    db.refresh(registro)
    return registro


@router.get("/mis-vacaciones", response_model=SaldoVacacionesOut)
def mis_vacaciones(db: Session = Depends(get_db), usuario: Usuario = Depends(requiere("autoservicio", "ver"))):
    return saldo_vacaciones(db, _empleado_de(usuario).id)


# ---- Solicitudes (vacaciones / permisos) con flujo de aprobación ----------
@router.get("/solicitudes", response_model=Pagina[SolicitudOut])
def listar_solicitudes(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                       usuario: Usuario = Depends(get_usuario_actual)):
    """Quien puede aprobar ve todas; el resto sólo las propias."""
    stmt = select(Solicitud)
    if not usuario.puede("rrhh", "aprobar"):
        if not usuario.puede("autoservicio", "ver"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sin acceso a solicitudes")
        stmt = stmt.where(Solicitud.empleado_id == _empleado_de(usuario).id)
    if p.q:
        stmt = stmt.where(Solicitud.empleado.has((Empleado.nombres + " " + Empleado.apellidos).ilike(f"%{p.q}%")))
    stmt = aplicar_filtros(stmt, request, {
        "estado": lambda v: Solicitud.estado == v,
        "tipo": lambda v: Solicitud.tipo == v,
        "empleado_id": igual(Solicitud.empleado_id),
    })
    stmt = aplicar_orden(stmt, p.orden, {"fecha_inicio": Solicitud.fecha_inicio, "created_at": Solicitud.created_at},
                         Solicitud.created_at.desc())
    return paginar(db, stmt, p)


@router.post("/solicitudes", response_model=SolicitudOut, status_code=status.HTTP_201_CREATED)
def crear_solicitud(datos: SolicitudCrear, db: Session = Depends(get_db),
                    usuario: Usuario = Depends(requiere("autoservicio", "crear"))):
    if datos.empleado_id is not None and datos.empleado_id != usuario.empleado_id:
        if not usuario.puede("rrhh", "crear"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sólo RRHH puede registrar solicitudes de otro empleado")
        empleado_id = obtener_o_404(db, Empleado, datos.empleado_id).id
    else:
        empleado_id = _empleado_de(usuario).id

    if datos.fecha_inicio < date.today() and datos.tipo == "vacaciones":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Las vacaciones no pueden solicitarse en fechas pasadas")
    dias = dias_habiles(datos.fecha_inicio, datos.fecha_fin)
    if dias == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El rango no contiene días hábiles")
    if datos.tipo == "vacaciones":
        validar_saldo(db, empleado_id, dias)

    solicitud = Solicitud(empleado_id=empleado_id, tipo=datos.tipo, fecha_inicio=datos.fecha_inicio,
                          fecha_fin=datos.fecha_fin, dias=dias, motivo=datos.motivo)
    db.add(solicitud)
    db.commit()   # la restricción EXCLUDE impide solapes con otra solicitud vigente
    db.refresh(solicitud)
    return solicitud


def _revisar(db: Session, id_: int, usuario: Usuario, estado: str, comentario: str | None) -> Solicitud:
    solicitud = db.scalar(select(Solicitud).where(Solicitud.id == id_).with_for_update(of=Solicitud))
    if solicitud is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    if solicitud.estado != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, f"La solicitud ya fue {solicitud.estado}")
    if solicitud.empleado_id == usuario.empleado_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No puede aprobar ni rechazar su propia solicitud")
    solicitud.estado = estado
    solicitud.revisado_por = usuario.id
    solicitud.fecha_revision = datetime.now(timezone.utc)
    solicitud.comentario_revision = comentario
    db.commit()
    db.refresh(solicitud)
    return solicitud


@router.post("/solicitudes/{id_}/aprobar", response_model=SolicitudOut)
def aprobar_solicitud(id_: int, datos: RevisionIn, db: Session = Depends(get_db),
                      usuario: Usuario = Depends(requiere("rrhh", "aprobar"))):
    return _revisar(db, id_, usuario, "aprobada", datos.comentario)


@router.post("/solicitudes/{id_}/rechazar", response_model=SolicitudOut)
def rechazar_solicitud(id_: int, datos: RevisionIn, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(requiere("rrhh", "aprobar"))):
    if not datos.comentario:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indique el motivo del rechazo")
    return _revisar(db, id_, usuario, "rechazada", datos.comentario)


@router.post("/solicitudes/{id_}/cancelar", response_model=SolicitudOut)
def cancelar_solicitud(id_: int, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(requiere("autoservicio", "crear"))):
    solicitud = obtener_o_404(db, Solicitud, id_)
    if solicitud.empleado_id != usuario.empleado_id and not usuario.puede("rrhh", "aprobar"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sólo puede cancelar sus propias solicitudes")
    if solicitud.estado != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Sólo se cancelan solicitudes pendientes")
    solicitud.estado = "cancelada"
    db.commit()
    db.refresh(solicitud)
    return solicitud
