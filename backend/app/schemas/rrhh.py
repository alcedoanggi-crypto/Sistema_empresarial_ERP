from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.comun import ORM, Dinero, MontoEntrada


# ---- Departamentos -------------------------------------------------------
class DepartamentoCrear(BaseModel):
    codigo: str = Field(pattern=r"^[A-Z0-9-]{2,10}$")
    nombre: str = Field(min_length=2, max_length=80)
    descripcion: str | None = Field(None, max_length=250)


class DepartamentoActualizar(BaseModel):
    codigo: str | None = Field(None, pattern=r"^[A-Z0-9-]{2,10}$")
    nombre: str | None = Field(None, min_length=2, max_length=80)
    descripcion: str | None = Field(None, max_length=250)


class DepartamentoOut(ORM):
    id: int
    codigo: str
    nombre: str
    descripcion: str | None
    created_at: datetime


# ---- Puestos -------------------------------------------------------------
class PuestoCrear(BaseModel):
    departamento_id: int
    nombre: str = Field(min_length=2, max_length=80)
    salario_min: MontoEntrada
    salario_max: MontoEntrada

    @model_validator(mode="after")
    def rango(self):
        if self.salario_max < self.salario_min:
            raise ValueError("El salario máximo debe ser mayor o igual al mínimo")
        return self


class PuestoActualizar(BaseModel):
    departamento_id: int | None = None
    nombre: str | None = Field(None, min_length=2, max_length=80)
    salario_min: MontoEntrada | None = None
    salario_max: MontoEntrada | None = None


class PuestoOut(ORM):
    id: int
    departamento_id: int
    departamento_nombre: str
    nombre: str
    salario_min: Dinero
    salario_max: Dinero


# ---- Empleados -----------------------------------------------------------
EstadoEmpleado = Literal["activo", "licencia", "inactivo"]


class EmpleadoBase(BaseModel):
    codigo: str = Field(min_length=2, max_length=12)
    cedula: str = Field(pattern=r"^[0-9]{10}$")
    nombres: str = Field(min_length=2, max_length=80)
    apellidos: str = Field(min_length=2, max_length=80)
    email: EmailStr
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=200)
    fecha_nacimiento: date
    fecha_ingreso: date
    fecha_salida: date | None = None
    puesto_id: int
    jefe_id: int | None = None
    salario: MontoEntrada
    dias_vacaciones_anuales: int = Field(15, ge=0, le=60)
    estado: EstadoEmpleado = "activo"


class EmpleadoCrear(EmpleadoBase):
    pass


class EmpleadoActualizar(BaseModel):
    codigo: str | None = Field(None, min_length=2, max_length=12)
    cedula: str | None = Field(None, pattern=r"^[0-9]{10}$")
    nombres: str | None = Field(None, min_length=2, max_length=80)
    apellidos: str | None = Field(None, min_length=2, max_length=80)
    email: EmailStr | None = None
    telefono: str | None = Field(None, max_length=20)
    direccion: str | None = Field(None, max_length=200)
    fecha_nacimiento: date | None = None
    fecha_ingreso: date | None = None
    fecha_salida: date | None = None
    puesto_id: int | None = None
    jefe_id: int | None = None
    salario: MontoEntrada | None = None
    dias_vacaciones_anuales: int | None = Field(None, ge=0, le=60)
    estado: EstadoEmpleado | None = None


class EmpleadoOut(ORM):
    id: int
    codigo: str
    cedula: str
    nombres: str
    apellidos: str
    nombre_completo: str
    email: str
    telefono: str | None
    direccion: str | None
    fecha_nacimiento: date
    fecha_ingreso: date
    fecha_salida: date | None
    puesto_id: int
    puesto_nombre: str
    departamento_id: int
    departamento_nombre: str
    jefe_id: int | None
    jefe_nombre: str | None
    salario: Dinero
    dias_vacaciones_anuales: int
    estado: str


# ---- Asistencia ----------------------------------------------------------
class AsistenciaCrear(BaseModel):
    empleado_id: int
    fecha: date
    hora_entrada: time
    hora_salida: time | None = None
    observacion: str | None = Field(None, max_length=200)


class AsistenciaActualizar(BaseModel):
    hora_entrada: time | None = None
    hora_salida: time | None = None
    observacion: str | None = Field(None, max_length=200)


class AsistenciaOut(ORM):
    id: int
    empleado_id: int
    empleado_nombre: str
    fecha: date
    hora_entrada: time
    hora_salida: time | None
    observacion: str | None
    atraso: bool


# ---- Solicitudes ---------------------------------------------------------
TipoSolicitud = Literal["vacaciones", "permiso", "licencia_medica", "otro"]


class SolicitudCrear(BaseModel):
    empleado_id: int | None = Field(None, description="Sólo RRHH puede crear para otro empleado")
    tipo: TipoSolicitud
    fecha_inicio: date
    fecha_fin: date
    motivo: str = Field(min_length=5, max_length=300)

    @model_validator(mode="after")
    def fechas(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha fin no puede ser anterior a la fecha inicio")
        return self


class RevisionIn(BaseModel):
    comentario: str | None = Field(None, max_length=300)


class SolicitudOut(ORM):
    id: int
    empleado_id: int
    empleado_nombre: str
    tipo: str
    fecha_inicio: date
    fecha_fin: date
    dias: int
    motivo: str
    estado: str
    revisado_por: int | None
    revisor_nombre: str | None
    fecha_revision: datetime | None
    comentario_revision: str | None
    created_at: datetime


class SaldoVacacionesOut(BaseModel):
    empleado_id: int
    empleado: str
    dias_asignados: int
    dias_tomados: int
    dias_pendientes: int
    dias_disponibles: int
