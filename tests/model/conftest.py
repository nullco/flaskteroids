import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from flaskteroids.model import Model, init
import flaskteroids.registry as registry


@pytest.fixture
def engine():
    return create_engine('sqlite:///:memory:')


@pytest.fixture(autouse=True)
def session(mocker, engine):
    Session = sessionmaker(bind=engine)
    from flaskteroids import model
    return mocker.patch.object(model, 'session', return_value=Session())


@pytest.fixture(autouse=True)
def current_app(mocker):
    from flaskteroids import model
    current_app = mocker.Mock()
    current_app.config = {'SECRET_KEY': 'test'}
    return mocker.patch.object(model, 'current_app', current_app)


@pytest.fixture(autouse=True)
def init_models(engine):
    def _(Base, model_base_tuples):
        Base.metadata.create_all(engine)
        registry.get(Model)['models'] = {model.__name__: model for _, model in model_base_tuples}
        for base, model in model_base_tuples:
            registry.get(model)['base_class'] = base
        for _, model in model_base_tuples:
            init(model)
    return _
