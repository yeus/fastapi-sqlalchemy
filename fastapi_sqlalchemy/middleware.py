from contextvars import ContextVar
from typing import Dict, Optional, Union

from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.types import ASGIApp

from fastapi_sqlalchemy.exceptions import MissingSessionError

_Session: sessionmaker = None
_session: ContextVar[Optional[Session]] = ContextVar("_session", default=None)


class DBSessionMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app: ASGIApp, db_url: Union[str, URL], engine_args: Dict = None, session_args: Dict = None,
    ):
        super().__init__(app)
        global _Session
        engine_args = engine_args or {}

        session_args = session_args or {}

        engine = create_engine(db_url, **engine_args)
        _Session = sessionmaker(bind=engine, **session_args)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        with db():
            response = await call_next(request)
        return response


class DBSessionMeta(type):
    # using this metaclass means that we can access db.session as a property at a class level,
    # rather than db().session
    @property
    def session(self):
        session = _session.get()
        if session is None:
            raise MissingSessionError
        return session


class DBSession(metaclass=DBSessionMeta):
    def __init__(self, session_args: Dict = None):
        self.token = None
        self.session_args = session_args or {}

    def __enter__(self):
        self.token = _session.set(_Session(**self.session_args))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        sess = _session.get()
        if exc_type is not None:
            sess.rollback()

        sess.close()
        _session.reset(self.token)


db = DBSession
