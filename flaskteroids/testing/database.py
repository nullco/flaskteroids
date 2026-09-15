from contextlib import contextmanager

from sqlalchemy.orm import scoped_session, sessionmaker


@contextmanager
def transactional_test(application):
    database = application.extensions["flaskteroids.db"]
    connection = database._engine.connect()
    transaction = connection.begin()
    original_factory = database._session_factory
    test_factory = scoped_session(
        sessionmaker(
            bind=connection,
            autoflush=False,
            join_transaction_mode="rollback_only",
        )
    )
    database._session_factory = test_factory
    try:
        yield
    finally:
        test_factory.remove()
        database._session_factory = original_factory
        if transaction.is_active:
            transaction.rollback()
        connection.close()
