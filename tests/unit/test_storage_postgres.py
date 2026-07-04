import pytest
from sqlalchemy import create_engine, text

from rhizonp.storage.postgres import (
    create_engine_from_settings,
    create_session_factory,
    session_scope,
)


def test_create_engine_from_settings_requires_database_url() -> None:
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_engine_from_settings("")


def test_session_scope_commits_and_rolls_back() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    session_factory = create_session_factory(engine)

    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))

    with session_scope(session_factory) as session:
        session.execute(text("INSERT INTO items (name) VALUES ('committed')"))

    with pytest.raises(RuntimeError, match="rollback"):
        with session_scope(session_factory) as session:
            session.execute(text("INSERT INTO items (name) VALUES ('rolled-back')"))
            raise RuntimeError("force rollback")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT name FROM items ORDER BY id")).fetchall()

    assert rows == [("committed",)]
