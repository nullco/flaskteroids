import logging

from flask import current_app, g
from werkzeug.local import LocalProxy

_logger = logging.getLogger(__name__)


def _get_session():
    if "db_session" not in g:
        _logger.debug("creating session")
        db = current_app.extensions["flaskteroids.db"]
        g.db_session = db.create_session()
    return g.db_session


session = LocalProxy(_get_session)
