from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

T = TypeVar("T")

# Decimal en Python (precisión exacta), número en JSON (cómodo para el frontend)
Dinero = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
MontoEntrada = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class Mensaje(BaseModel):
    detail: str
