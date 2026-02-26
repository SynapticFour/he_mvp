# SPDX-License-Identifier: Apache-2.0
"""Database and session tests."""
from app.database import create_db_and_tables, engine, get_session
from sqlalchemy import text


def test_create_db_and_tables():
    create_db_and_tables()
    with engine.connect() as conn:
        r = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='studies'"))
        row = r.fetchone()
    assert row is not None
    assert row[0] == "studies"


def test_get_session_generator():
    gen = get_session()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass
