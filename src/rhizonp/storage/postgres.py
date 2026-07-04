from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from rhizonp.config import get_settings


def create_engine_from_settings(database_url: str | None = None, *, echo: bool = False) -> Engine:
    resolved_url = database_url or get_settings().database_url
    if not resolved_url:
        raise RuntimeError(
            "DATABASE_URL is required to create a SQLAlchemy engine. "
            "Set it in .env or pass database_url explicitly."
        )
    return create_engine(resolved_url, echo=echo, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
