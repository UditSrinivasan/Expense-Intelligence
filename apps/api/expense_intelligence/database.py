from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


@event.listens_for(Session, "after_begin")
def restore_request_rls_context(session: Session, _transaction, connection) -> None:
    """Reapply transaction-local identity after endpoint commits on pooled PostgreSQL."""
    if connection.dialect.name != "postgresql" or not session.info.get("auth_subject"):
        return
    connection.execute(text("select set_config('app.auth_subject', :value, true)"), {"value": session.info["auth_subject"]})
    if session.info.get("current_user_id"):
        connection.execute(text("select set_config('app.current_user_id', :value, true)"), {"value": session.info["current_user_id"]})
    if session.info.get("current_user_email"):
        connection.execute(text("select set_config('app.current_user_email', :value, true)"), {"value": session.info["current_user_email"]})


def build_engine(url: str | None = None):
    database_url = url or get_settings().database_url
    if database_url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
    else:
        settings = get_settings()
        kwargs = {
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
            "pool_recycle": settings.database_pool_recycle_seconds,
        }
    return create_engine(database_url, pool_pre_ping=True, **kwargs)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
