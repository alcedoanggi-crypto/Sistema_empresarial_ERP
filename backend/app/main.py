from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.core.errores import manejar_error_bd
from app.routers import auth, compras, general, inventario, rrhh, seguridad, ventas

app = FastAPI(
    title="Sistema de Administración Empresarial",
    description="ERP ligero: RRHH, inventario, compras, ventas, dashboard, reportes y auditoría.",
    version="1.0.0",
)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_lista, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Content-Disposition"])
app.add_exception_handler(DBAPIError, manejar_error_bd)

app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(seguridad.router, prefix="/api/seguridad", tags=["Usuarios y roles"])
app.include_router(rrhh.router, prefix="/api/rrhh", tags=["Recursos Humanos"])
app.include_router(inventario.router, prefix="/api/inventario", tags=["Inventario"])
app.include_router(compras.router, prefix="/api/compras", tags=["Compras"])
app.include_router(ventas.router, prefix="/api/ventas", tags=["Ventas"])
app.include_router(general.router, prefix="/api", tags=["Dashboard, reportes y auditoría"])


@app.get("/api/salud", tags=["Sistema"])
def salud():
    return {"estado": "ok"}
