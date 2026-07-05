from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from rhizonp.config import get_settings
from rhizonp.storage.postgres import create_engine_from_settings


def is_prod_mode() -> bool:
    return get_settings().runtime_mode == "prod"


def prod_runtime_error_message(action: str) -> str:
    return (
        f"{action} requires a configured PostgreSQL DATABASE_URL in production mode "
        f"(RHIZONP_RUNTIME_MODE=prod)."
    )


def create_runtime_engine(*, allow_sqlite_fallback: bool = True) -> Engine:
    try:
        return create_engine_from_settings()
    except RuntimeError as exc:
        if is_prod_mode() or not allow_sqlite_fallback:
            raise RuntimeError(prod_runtime_error_message("This operation")) from exc
        return create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
