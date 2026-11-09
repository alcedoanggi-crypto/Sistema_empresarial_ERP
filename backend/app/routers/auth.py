from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_usuario_actual
from app.core.seguridad import crear_token, hash_password, verificar_password
from app.database import get_db
from app.models import Usuario
from app.schemas.seguridad import CambioPasswordIn, LoginIn, SesionOut, TokenOut

router = APIRouter()


def _sesion(usuario: Usuario) -> dict:
    return {"usuario": usuario, "permisos": usuario.permisos_dict()}


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    usuario = db.scalar(
        select(Usuario).where(func.lower(Usuario.email) == datos.email.lower(), Usuario.deleted_at.is_(None))
    )
    # Mismo mensaje para "no existe" y "clave incorrecta": no revela qué correos existen
    if usuario is None or not verificar_password(datos.password, usuario.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    if not usuario.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario desactivado. Contacte al administrador")

    usuario.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    return {"access_token": crear_token(usuario.id), **_sesion(usuario)}


@router.get("/me", response_model=SesionOut)
def me(usuario: Usuario = Depends(get_usuario_actual)):
    return _sesion(usuario)


@router.post("/cambiar-password", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_password(datos: CambioPasswordIn, usuario: Usuario = Depends(get_usuario_actual),
                     db: Session = Depends(get_db)):
    if not verificar_password(datos.actual, usuario.password_hash):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "La contraseña actual no es correcta")
    usuario.password_hash = hash_password(datos.nueva)
    db.commit()
