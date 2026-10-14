from contextlib import contextmanager
from contextvars import Context, ContextVar

from sqlalchemy.orm import sessionmaker


@contextmanager
def transactional_test(application):
    database = application.extensions["flaskteroids.db"]
    connection = database._engine.connect()
    transaction = connection.begin()
    original_factory = database._session_factory
    original_wsgi_app = application.wsgi_app
    sessions = []
    request_sessions = ContextVar("flaskteroids_request_sessions", default=None)
    factory = sessionmaker(
        bind=connection,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    def test_factory():
        session = factory()
        owned = request_sessions.get()
        (sessions if owned is None else owned).append(session)
        return session

    def close_sessions(owned):
        for session in owned:
            session.close()
        owned.clear()

    def isolated_request(environ, start_response):
        context = Context()
        owned = []
        context.run(request_sessions.set, owned)
        try:
            response = context.run(original_wsgi_app, environ, start_response)
        except BaseException:
            close_sessions(owned)
            raise
        return _ContextResponse(response, context, lambda: close_sessions(owned))

    database._session_factory = test_factory
    application.wsgi_app = isolated_request
    try:
        yield
    finally:
        application.wsgi_app = original_wsgi_app
        close_sessions(sessions)
        database._session_factory = original_factory
        if transaction.is_active:
            transaction.rollback()
        connection.close()


class _ContextResponse:
    def __init__(self, response, context, cleanup):
        self.response = response
        self.iterator = iter(response)
        self.context = context
        self.cleanup = cleanup

    def __iter__(self):
        return self

    def __next__(self):
        return self.context.run(next, self.iterator)

    def close(self):
        try:
            close = getattr(self.response, "close", None)
            if close is not None:
                self.context.run(close)
        finally:
            self.context.run(self.cleanup)
