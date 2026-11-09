from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://empresa_app:empresa_pass@localhost:5432/sistema_empresarial"
    jwt_secret: str = "cambia-esta-clave-en-produccion"
    jwt_algoritmo: str = "HS256"
    jwt_expira_minutos: int = 480
    tasa_iva: Decimal = Decimal("15")
    cors_origins: str = "http://localhost:5173"
    nombre_empresa: str = "Empresa Demo S.A."

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
