from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.comun import ORM


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class CambioPasswordIn(BaseModel):
    actual: str
    nueva: str = Field(min_length=8, max_length=72)


class UsuarioOut(ORM):
    id: int
    nombre: str
    email: str
    rol_id: int
    rol_nombre: str
    empleado_id: int | None
    empleado_nombre: str | None
    activo: bool
    ultimo_acceso: datetime | None
    created_at: datetime


class SesionOut(BaseModel):
    usuario: UsuarioOut
    permisos: dict[str, dict[str, bool]]


class TokenOut(SesionOut):
    access_token: str
    token_type: str = "bearer"


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    rol_id: int
    empleado_id: int | None = None
    activo: bool = True


class UsuarioActualizar(BaseModel):
    nombre: str | None = Field(None, min_length=3, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=72)
    rol_id: int | None = None
    empleado_id: int | None = None
    activo: bool | None = None


class PermisoIO(BaseModel):
    modulo_id: int
    modulo_clave: str | None = None
    modulo_nombre: str | None = None
    puede_ver: bool = False
    puede_crear: bool = False
    puede_editar: bool = False
    puede_eliminar: bool = False
    puede_aprobar: bool = False


class RolOut(ORM):
    id: int
    nombre: str
    descripcion: str | None
    es_sistema: bool


class RolCrear(BaseModel):
    nombre: str = Field(pattern=r"^[a-z_]{3,30}$")
    descripcion: str | None = Field(None, max_length=200)


class RolActualizar(BaseModel):
    descripcion: str | None = Field(None, max_length=200)


class ModuloOut(ORM):
    id: int
    clave: str
    nombre: str
