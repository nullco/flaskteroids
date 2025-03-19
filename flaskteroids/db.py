from sqlalchemy.ext.automap import automap_base
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session
from importlib import import_module
from flask import g, current_app
import logging
import pkgutil
import inspect
import flaskteroids.registry as registry

_logger = logging.getLogger(__name__)


def session():
    if 'db_session' not in g:
        _logger.debug('creating session')
        db = current_app.extensions['flaskteroids.db']
        g.db_session = db.create_session()
    return g.db_session


def init(app):
    return Database(app)


class Database:

    def __init__(self, app):
        self._engine = create_engine(app.config['DATABASE_URL'])
        self._metadata = MetaData()
        self._session_factory = scoped_session(sessionmaker(bind=self._engine))
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

    def _discover_models(self):
        models_package = 'app.models'
        package = import_module(models_package)
        package_path = package.__path__
        models = {}
        model = import_module('flaskteroids.model')
        for _, model_name, _ in pkgutil.iter_modules(package_path):
            absolute_name = f"{models_package}.{model_name}"
            module = import_module(absolute_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, model.Model) and \
                        obj is not model.Model:
                    models[name] = obj
        _logger.debug(f'discovered {len(models)} model classes')
        return models

    def create_session(self):
        return self._session_factory()

    @property
    def models(self):
        return self._models

    def init_models(self):
        self._models = self._discover_models()
        self._metadata.reflect(self._engine)
        Base = automap_base(metadata=self._metadata)
        Base.prepare()
        for name, model in self._models.items():
            table_name = _pluralize(name.lower())
            if hasattr(Base.classes, table_name):
                ns = registry.get(model)
                ns['base_class'] = getattr(Base.classes, table_name)


def _pluralize(name):
    return f'{name}s'
