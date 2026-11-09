from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_SQL_CONTEXTO = text(
    "SELECT set_config('app.usuario_id', :usuario, true), set_config('app.ip', :ip, true)"
)


def _contexto_auditoria(session: Session, transaction, connection) -> None:
    """Al iniciar CADA transacción, informa a PostgreSQL quién está operando.

    El trigger fn_auditoria lee estos valores con current_setting(). Se usan
    variables locales a la transacción (tercer argumento = true), así una
    conexión reutilizada del pool nunca hereda el usuario de otra petición.
    """
    usuario = session.info.get("usuario_id")
    if usuario is not None:
        connection.execute(_SQL_CONTEXTO, {"usuario": str(usuario), "ip": session.info.get("ip") or ""})


event.listen(SessionLocal, "after_begin", _contexto_auditoria)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
