from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.services.ports import UnitOfWork

_active_session: ContextVar[Session | None] = ContextVar("postgres_uow_session", default=None)


@contextmanager
def repo_session(engine: Engine) -> Iterator[Session]:
    current = _active_session.get()
    if current is not None:
        yield current
        return
    session = Session(engine)
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def finish_write(session: Session) -> None:
    if _active_session.get() is session:
        session.flush()
        return
    session.commit()


class PostgresUnitOfWork(UnitOfWork):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._session: Session | None = None
        self._token = None

    def active(self) -> bool:
        return self._session is not None

    def begin(self) -> None:
        if self._session is not None:
            return
        self._session = Session(self._engine)
        self._token = _active_session.set(self._session)

    def commit(self) -> None:
        if self._session is None:
            return
        self._session.commit()
        self._session.close()
        if self._token is not None:
            _active_session.reset(self._token)
        self._session = None
        self._token = None

    def rollback(self) -> None:
        if self._session is None:
            return
        self._session.rollback()
        self._session.close()
        if self._token is not None:
            _active_session.reset(self._token)
        self._session = None
        self._token = None
