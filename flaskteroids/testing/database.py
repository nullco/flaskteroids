from contextlib import contextmanager
from contextvars import Context, ContextVar

from sqlalchemy.orm import scoped_session, sessionmaker


@contextmanager
def transactional_test(application):
    database = application.extensions["flaskteroids.db"]
    connection = database._engine.connect()
    transaction = connection.begin()
    original_factory = database._session_factory
    original_wsgi_app = application.wsgi_app
    session_scope = ContextVar("flaskteroids_test_session_scope", default=None)
    test_factory = scoped_session(
        sessionmaker(
            bind=connection,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        ),
        scopefunc=session_scope.get,
    )

    def isolated_request(environ, start_response):
        context = Context()
        context.run(session_scope.set, object())
        try:
            response = context.run(original_wsgi_app, environ, start_response)
        except BaseException:
            context.run(test_factory.remove)
            raise
        return _ContextResponse(response, context, test_factory.remove)

    database._session_factory = test_factory
    application.wsgi_app = isolated_request
    try:
        yield
    finally:
        application.wsgi_app = original_wsgi_app
        test_factory.remove()
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
