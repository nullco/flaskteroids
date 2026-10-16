import logging
from contextlib import contextmanager
from functools import partial, wraps

from flask import current_app, g
from sqlalchemy import event
from sqlalchemy.orm import Session, SessionTransactionOrigin
from werkzeug.local import LocalProxy

_logger = logging.getLogger(__name__)


def _get_session():
    if "db_session" not in g:
        _logger.debug("creating session")
        db = current_app.extensions["flaskteroids.db"]
        g.db_session = db.create_session()
    return g.db_session


session = LocalProxy(_get_session)

_BOUNDARY = "flaskteroids.transaction"


@event.listens_for(Session, "after_transaction_create")
def _remember_savepoint(db_session, boundary):
    if boundary.nested:
        db_session.info[_BOUNDARY] = db_session.get_transaction()


@event.listens_for(Session, "after_transaction_end")
def _forget_boundary(db_session, boundary):
    if db_session.info.get(_BOUNDARY) is boundary:
        db_session.info.pop(_BOUNDARY)


def _explicit_transaction(db_session):
    current = db_session.get_transaction()
    return current is not None and (
        current.origin is not SessionTransactionOrigin.AUTOBEGIN
        or db_session.info.get(_BOUNDARY) is current
        or db_session.get_nested_transaction() is not None
    )


@contextmanager
def transaction(*, requires_new=False):
    """Join an explicit transaction, or own one until this block finishes.

    Implicit transactions opened by reads are adopted, not mistaken for an
    application-owned boundary. ``requires_new`` uses a savepoint when joining
    an existing explicit transaction.
    """
    db_session = _get_session()
    if _explicit_transaction(db_session):
        if requires_new:
            with db_session.begin_nested() as boundary:
                yield boundary
        else:
            yield db_session.get_nested_transaction() or db_session.get_transaction()
        return
    boundary = db_session.get_transaction() or db_session.begin()
    db_session.info[_BOUNDARY] = boundary
    try:
        with boundary:
            yield boundary
    finally:
        try:
            boundary.close()
        finally:
            db_session.info.pop(_BOUNDARY, None)


def transactional(operation=None, *, rollback_on_false=False):
    """Commit standalone persistence, optionally rejecting false model results."""
    if operation is None:
        return partial(transactional, rollback_on_false=rollback_on_false)

    @wraps(operation)
    def wrapped(*args, **kwargs):
        owned = not _explicit_transaction(_get_session())
        with transaction() as boundary:
            result = operation(*args, **kwargs)
            if rollback_on_false and result is False and owned:
                boundary.rollback()
            return result

    return wrapped
