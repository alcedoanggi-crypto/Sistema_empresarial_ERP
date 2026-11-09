from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session


def dias_habiles(inicio: date, fin: date) -> int:
    """Días de lunes a viernes entre dos fechas, ambas inclusive."""
    total = 0
    actual = inicio
    while actual <= fin:
        if actual.weekday() < 5:
            total += 1
        actual += timedelta(days=1)
    return total


def saldo_vacaciones(db: Session, empleado_id: int) -> dict | None:
    fila = db.execute(
        text("SELECT * FROM v_saldo_vacaciones WHERE empleado_id = :id"), {"id": empleado_id}
    ).mappings().first()
    return dict(fila) if fila else None


def validar_saldo(db: Session, empleado_id: int, dias: int) -> None:
    saldo = saldo_vacaciones(db, empleado_id)
    disponibles = saldo["dias_disponibles"] if saldo else 0
    if dias > disponibles:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Saldo de vacaciones insuficiente: solicita {dias} días hábiles y dispone de {disponibles}",
        )
