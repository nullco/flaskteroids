import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from flaskteroids.testing.storage import temporary_storage


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "system: browser-driven Flaskteroids system test"
    )


def pytest_sessionstart(session):
    os.environ.setdefault("FLASKTEROIDS_ENV", "test")
    session.config._flaskteroids_worker_database = _configure_worker_database()
    _prepare_test_database(session.config.rootpath)


def pytest_sessionfinish(session, exitstatus):
    database = getattr(session.config, "_flaskteroids_worker_database", None)
    if database:
        database.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def application():
    environment = importlib.import_module("config.environment")
    application = environment.application
    application.config["TESTING"] = True
    if not application.config.get("SERVER_NAME"):
        application.config["SERVER_NAME"] = "localhost"
    return application


@pytest.fixture
def app(application):
    return application


@pytest.fixture
def client(application):
    return application.test_client()


@pytest.fixture(autouse=True)
def attachment_storage(application):
    with temporary_storage(application) as storage:
        yield storage


def _configure_worker_database():
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker or os.environ.get("DATABASE_URL"):
        return None
    path = Path("storage", f"test-{worker}.sqlite3").resolve()
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    return path


def _prepare_test_database(root):
    migration_config = Path(root, "db", "migrate", "alembic.ini")
    if not migration_config.exists():
        return
    environment = os.environ.copy()
    environment.setdefault("FLASK_APP", "wsgi.py")
    result = subprocess.run(
        [sys.executable, "-m", "flask", "db:migrate"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            "Unable to prepare the Flaskteroids test database:\n"
            f"{result.stdout}{result.stderr}"
        )
