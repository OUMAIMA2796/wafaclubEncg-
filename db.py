"""Connexion base de données (SQLite par défaut, PostgreSQL supporté)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .base import Base
from .config import BASE_DIR, settings


def _sqlite_absolute_url(url: str) -> str:
    """Résout un fichier SQLite relatif depuis la racine du projet."""
    if not url.startswith("sqlite:///") or ":memory:" in url:
        return url
    raw = url[len("sqlite:///") :]
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        return url
    absolute = (BASE_DIR / raw).resolve()
    absolute.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{absolute.as_posix()}"


class Database:
    def __init__(self, url: str | None = None) -> None:
        self.url = _sqlite_absolute_url(url or settings.database_url)
        engine_kwargs: dict = {"future": True, "pool_pre_ping": True}
        if self.url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in self.url:
                engine_kwargs["poolclass"] = StaticPool
            else:
                path = self.url.removeprefix("sqlite:///")
                Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(self.url, **engine_kwargs)
        if self.url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False, autoflush=False, future=True)

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ARG004
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def create_all(self) -> None:
        from . import models  # noqa: F401  # enregistre les tables auprès du Base

        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        from . import models  # noqa: F401

        Base.metadata.drop_all(self.engine)

    def reset(self) -> None:
        self.drop_all()
        self.create_all()

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


database = Database()
