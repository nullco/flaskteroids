from flask import g, current_app
import logging


_logger = logging.getLogger(__name__)


def session():
    if 'db_session' not in g:
        _logger.debug('creating session')
        db = current_app.extensions['flaskteroids.db']
        g.db_session = db.create_session()
    return g.db_session
