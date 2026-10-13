import logging

from flask import g
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import scoped_session, sessionmaker

from flaskteroids import registry
from flaskteroids.discovery import discover_classes
from flaskteroids.inflector import inflector
from flaskteroids.model import Model, init

_logger = logging.getLogger(__name__)


def _enable_sqlite_foreign_keys(connection, connection_record):
    autocommit = connection.autocommit
    connection.autocommit = True
    try:
        cursor = connection.cursor()
        try:
            cursor.execute('PRAGMA foreign_keys=ON')
        finally:
            cursor.close()
    finally:
        connection.autocommit = autocommit


class SQLAlchemyExtension:

    def __init__(self, app):
        if app:
            self.init_app(app)

    def init_app(self, app):
        options = {}
        if make_url(app.database_url).get_backend_name() == 'sqlite':
            options['connect_args'] = {'autocommit': False}
        self._engine = create_engine(app.database_url, **options)
        if options:
            event.listen(self._engine, 'connect', _enable_sqlite_foreign_keys)
        self._models_module = app.config.paths.models
        self._metadata = MetaData()
        self._session_factory = scoped_session(sessionmaker(bind=self._engine, autoflush=False))
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['flaskteroids.db'] = self

        self.init_models()

        @app.teardown_appcontext
        def _(exception=None):
            db_session = g.get('db_session')
            if db_session is None:
                return
            try:
                if exception is not None:
                    _logger.debug('rolling transaction due to error')
                    db_session.rollback()
                else:
                    _logger.debug('committing transaction')
                    db_session.commit()
            finally:
                _logger.debug('closing session')
                try:
                    db_session.close()
                finally:
                    g.pop('db_session', None)

    def create_session(self):
        return self._session_factory()

    def new_session(self):
        return self._session_factory.session_factory()

    @property
    def models(self):
        return self._models

    def init_models(self):
        models = discover_classes(self._models_module, Model, {'ApplicationModel'})
        ns = registry.get(Model)
        ns['models'] = models
        self._models = models
        tables = [self._get_table_name(name) for name in self._models]
        try:
            self._metadata.reflect(self._engine, only=tables)
        except InvalidRequestError:
            pass
        Base = automap_base(metadata=self._metadata)
        Base.prepare(generate_relationship=self._skip_relationships)
        for name, model in self._models.items():
            table_name = self._get_table_name(name)
            if hasattr(Base.classes, table_name):
                _logger.debug(f'associating <{table_name}> to model <{name}>')
                ns = registry.get(model)
                ns['base_class'] = getattr(Base.classes, table_name)
        for model in self._models.values():
            init(model)

    def _get_table_name(self, model_name):
        return inflector.tableize(model_name)

    @staticmethod
    def _skip_relationships(*args, **kwargs):
        # We don't want to automap relationships at this moment
        # Those will be done explicitly afterwards
        pass
