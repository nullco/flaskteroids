from sqlalchemy import create_engine
from flaskteroids.app import create_app
import pytest


@pytest.fixture
def app():

    # This is needed in order to share in-memory DB from different engines
    # One engine that inits the DB with some tables
    # A second engine that actually auto-maps model to existing tables in the DB

    db_url = "sqlite:///file::memory:?cache=shared&uri=true"

    init_db(db_url)

    cfg = {
        'MODELS': {'LOCATION': 'tests.app.models'},
        'VEWS': {'LOCATION': 'app/views/'},
        'CONTROLLERS': {'LOCATION': 'tests.app.controllers'},
        'ROUTES': {'LOCATION': 'tests.app.config.routes'},
        'DB': {'SQLALCHEMY_URL': db_url},
        'JOBS': {
            'LOCATION': 'tests.app.jobs',
            'CELERY_BROKER_URL': 'sqla+sqlite:///:memory:'
        },
        'MAILERS': {'SEND_MAILS': False}
    }
    app = create_app(__name__, cfg)
    return app


@pytest.fixture
def app_ctx(app):
    with app.app_context():
        yield


def init_db(db_url):
    from sqlalchemy.orm import declarative_base
    from sqlalchemy import Column, ForeignKey, Integer, String

    engine = create_engine(db_url)

    Base = declarative_base()

    class UserBase(Base):
        __tablename__ = 'users'

        id = Column(Integer(), primary_key=True, autoincrement=True)
        username = Column(String())
        group_id = Column(Integer(), ForeignKey('groups.id'))

    class GroupBase(Base):
        __tablename__ = 'groups'

        id = Column(Integer(), primary_key=True, autoincrement=True)
        name = Column(String())

    Base.metadata.create_all(engine)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def cli_runner(app):
    return app.test_cli_runner()
