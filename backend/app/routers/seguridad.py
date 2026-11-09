from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.crud import Paginacion, aplicar_busqueda, aplicar_filtros, aplicar_orden, booleano, igual, \
    obtener_o_404, paginar
from app.core.deps import requiere
from app.core.seguridad import hash_password
from app.database import get_db
from app.models import Modulo, Permiso, Rol, Usuario
from app.schemas.comun import Pagina
from app.schemas.seguridad import ModuloOut, PermisoIO, RolActualizar, RolCrear, RolOut, UsuarioActualizar, \
    UsuarioCrear, UsuarioOut

router = APIRouter()
ROL_ADMIN = "administrador"


# ---- Usuarios ------------------------------------------------------------
@router.get("/usuarios", response_model=Pagina[UsuarioOut])
def listar_usuarios(request: Request, p: Paginacion = Depends(), db: Session = Depends(get_db),
                    _=Depends(requiere("usuarios", "ver"))):
    stmt = select(Usuario).where(Usuario.deleted_at.is_(None))
    stmt = aplicar_busqueda(stmt, p.q, [Usuario.nombre, Usuario.email])
    stmt = aplicar_filtros(stmt, request, {"rol_id": igual(Usuario.rol_id), "activo": booleano(Usuario.activo)})
    stmt = aplicar_orden(stmt, p.orden, {"nombre": Usuario.nombre, "email": Usuario.email,
                                         "ultimo_acceso": Usuario.ultimo_acceso}, Usuario.nombre)
    return paginar(db, stmt, p)


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCrear, db: Session = Depends(get_db), _=Depends(requiere("usuarios", "crear"))):
    valores = datos.model_dump()
    usuario = Usuario(password_hash=hash_password(valores.pop("password")), **valores)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.put("/usuarios/{id_}", response_model=UsuarioOut)
def actualizar_usuario(id_: int, datos: UsuarioActualizar, db: Session = Depends(get_db),
                       actual: Usuario = Depends(requiere("usuarios", "editar"))):
    usuario = obtener_o_404(db, Usuario, id_)
    valores = datos.model_dump(exclude_unset=True)
    if usuario.id == actual.id and (valores.get("activo") is False or
                                    ("rol_id" in valores and valores["rol_id"] != usuario.rol_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "No puede desactivarse ni cambiarse el rol a sí mismo")
    if "password" in valores:
        password = valores.pop("password")
        if password:
            usuario.password_hash = hash_password(password)
    for campo, valor in valores.items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/usuarios/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(id_: int, db: Session = Depends(get_db),
                     actual: Usuario = Depends(requiere("usuarios", "eliminar"))):
    usuario = obtener_o_404(db, Usuario, id_)
    if usuario.id == actual.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puede eliminar su propio usuario")
    usuario.deleted_at = datetime.now(timezone.utc)
    usuario.activo = False
    db.commit()


# ---- Roles y permisos ----------------------------------------------------
@router.get("/modulos", response_model=list[ModuloOut])
def listar_modulos(db: Session = Depends(get_db), _=Depends(requiere("usuarios", "ver"))):
    return db.scalars(select(Modulo).order_by(Modulo.orden)).all()


@router.get("/roles", response_model=list[RolOut])
def listar_roles(db: Session = Depends(get_db), _=Depends(requiere("usuarios", "ver"))):
    return db.scalars(select(Rol).order_by(Rol.id)).all()


@router.post("/roles", response_model=RolOut, status_code=status.HTTP_201_CREATED)
def crear_rol(datos: RolCrear, db: Session = Depends(get_db), _=Depends(requiere("usuarios", "crear"))):
    if db.scalar(select(Rol).where(Rol.nombre == datos.nombre)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un rol con ese nombre")
    rol = Rol(**datos.model_dump())
    db.add(rol)
    db.commit()
    db.refresh(rol)
    return rol


@router.put("/roles/{id_}", response_model=RolOut)
def actualizar_rol(id_: int, datos: RolActualizar, db: Session = Depends(get_db),
                   _=Depends(requiere("usuarios", "editar"))):
    rol = obtener_o_404(db, Rol, id_)
    rol.descripcion = datos.descripcion
    db.commit()
    return rol


@router.delete("/roles/{id_}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_rol(id_: int, db: Session = Depends(get_db), _=Depends(requiere("usuarios", "eliminar"))):
    rol = obtener_o_404(db, Rol, id_)
    if rol.es_sistema:
        raise HTTPException(status.HTTP_409_CONFLICT, "Los roles del sistema no se pueden eliminar")
    en_uso = db.scalar(select(func.count()).where(Usuario.rol_id == id_, Usuario.deleted_at.is_(None)))
    if en_uso:
        raise HTTPException(status.HTTP_409_CONFLICT, f"El rol está asignado a {en_uso} usuario(s)")
    db.delete(rol)
    db.commit()


@router.get("/roles/{id_}/permisos", response_model=list[PermisoIO])
def permisos_rol(id_: int, db: Session = Depends(get_db), _=Depends(requiere("usuarios", "ver"))):
    rol = obtener_o_404(db, Rol, id_)
    actuales = {p.modulo_id: p for p in rol.permisos}
    matriz = []
    for m in db.scalars(select(Modulo).order_by(Modulo.orden)):
        p = actuales.get(m.id)
        matriz.append(PermisoIO(
            modulo_id=m.id, modulo_clave=m.clave, modulo_nombre=m.nombre,
            **({k: getattr(p, k) for k in PermisoIO.model_fields if k.startswith("puede_")} if p else {}),
        ))
    return matriz


@router.put("/roles/{id_}/permisos", response_model=list[PermisoIO])
def guardar_permisos(id_: int, matriz: list[PermisoIO], db: Session = Depends(get_db),
                     _=Depends(requiere("usuarios", "editar"))):
    rol = obtener_o_404(db, Rol, id_)
    if rol.nombre == ROL_ADMIN:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Los permisos del administrador son fijos (evita quedar sin acceso al sistema)")
    actuales = {p.modulo_id: p for p in rol.permisos}
    for fila in matriz:
        valores = fila.model_dump(include={k for k in PermisoIO.model_fields if k.startswith("puede_")})
        # 'ver' es requisito de cualquier otra acción (también lo exige ck_permisos_ver)
        if any(v for k, v in valores.items() if k != "puede_ver"):
            valores["puede_ver"] = True
        permiso = actuales.get(fila.modulo_id)
        if permiso is None:
            rol.permisos.append(Permiso(modulo_id=fila.modulo_id, **valores))
        else:
            for k, v in valores.items():
                setattr(permiso, k, v)
    db.commit()
    db.expire(rol)
    return permisos_rol(id_, db)
