from sqlalchemy.ext.automap import automap_base
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, scoped_session
from importlib import import_module
from flask import g
import logging
import pkgutil
import inspect

_logger = logging.getLogger('flaskteroids.db')


def session():
    return g.db_session


def configure(app):
    engine = create_engine(app.config['DATABASE_URL'])
    SessionLocal = scoped_session(sessionmaker(bind=engine))
    metadata = MetaData()

    models = _discover_models('app.models')
    metadata.reflect(engine, only=list(models.keys()))
    Base = automap_base(metadata=metadata)
    Base.prepare()
    for table_name, model in models.items():
        if hasattr(Base.classes, table_name):
            model.__init_base__(getattr(Base.classes, table_name))

    @app.before_request
    def _():
        _logger.debug('creating session for request')
        g.db_session = SessionLocal()

    @app.teardown_request
    def _(exception=None):
        _logger.debug('closing session for request')
        if exception:
            g.db_session.rollback()
        else:
            g.db_session.commit()
        g.db_session.close()


def _discover_models(models_package):
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
                models[_pluralize(name.lower())] = obj
    _logger.debug(f'discovered {len(models)} model classes')
    return models


def _pluralize(name):
    return f'{name}s'
