import logging
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session
from flask import g
from flaskteroids.discovery import discover_classes
import flaskteroids.registry as registry
from flaskteroids.model import Model, init
from flaskteroids.inflector import inflector


_logger = logging.getLogger(__name__)


class SQLAlchemyExtension:

    def __init__(self, app):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._engine = create_engine(app.config['DB']['SQLALCHEMY_URL'])
        self._models_module = app.config['MODELS']['LOCATION']
        self._metadata = MetaData()
        self._session_factory = scoped_session(sessionmaker(bind=self._engine, autoflush=False))
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['flaskteroids.db'] = self

        self.init_models()

        @app.teardown_appcontext
        def _(exception=None):
            db_session = g.pop('db_session', None)
            if db_session:
                if exception:
                    _logger.debug('rolling transaction due to error')
                    db_session.rollback()
                else:
                    _logger.debug('committing transaction')
                    db_session.commit()
                _logger.debug('closing session')
                db_session.close()

    def create_session(self):
        return self._session_factory()

    @property
    def models(self):
        return self._models

    def init_models(self):
        models = discover_classes(self._models_module, Model, {'ApplicationModel'})
        ns = registry.get(Model)
        ns['models'] = models
        self._models = models
        tables = [self._get_table_name(name) for name in self._models.keys()]
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
