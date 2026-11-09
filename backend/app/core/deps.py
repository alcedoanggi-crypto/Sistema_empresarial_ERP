import ipaddress

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.seguridad import decodificar_token
from app.database import get_db
from app.models import Usuario

_bearer = HTTPBearer(auto_error=False)


def _ip_valida(request: Request) -> str | None:
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def get_usuario_actual(
    request: Request,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    no_autorizado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada",
                                  headers={"WWW-Authenticate": "Bearer"})
    usuario_id = decodificar_token(cred.credentials) if cred else None
    if usuario_id is None:
        raise no_autorizado

    # IMPORTANTE: se fija el contexto de auditoría ANTES de la primera consulta,
    # porque es al abrir la transacción cuando se ejecuta set_config().
    db.info["usuario_id"] = usuario_id
    db.info["ip"] = _ip_valida(request)

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo or usuario.deleted_at is not None:
        raise no_autorizado
    return usuario


def requiere(modulo: str, accion: str = "ver"):
    """Dependencia de autorización: requiere('inventario', 'crear')."""

    def verificar(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        if not usuario.puede(modulo, accion):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"No tiene permiso para '{accion}' en el módulo '{modulo}'")
        return usuario

    return verificar
