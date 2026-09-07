from pathlib import Path
from sqlalchemy import create_engine
from flaskteroids.application import Application
import pytest


@pytest.fixture
def app():

    # This is needed in order to share in-memory DB from different engines
    # One engine that inits the DB with some tables
    # A second engine that actually auto-maps model to existing tables in the DB

    db_url = "sqlite:///file::memory:?cache=shared&uri=true"

    init_db(db_url)

    class TestApplication(Application):
        def configure(self, config):
            config.load_defaults('0.1')
            config.paths.models = 'tests.app.models'
            config.paths.views = 'app/views'
            config.paths.controllers = 'tests.app.controllers'
            config.paths.routes = 'tests.app.config.routes'
            config.paths.jobs = 'tests.app.jobs'
            config.paths.mailers = 'tests.app.mailers'
            config.active_job.broker_url = 'sqla+sqlite:///:memory:'
            config.action_mailer.perform_deliveries = False

        def _configure_database(self):
            self.database_url = db_url

    return TestApplication.initialize(
        environment='test',
        root_path=Path(__file__).parent,
    )


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
