import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


@pytest.fixture
def preparation_app(tmp_path):
    root = tmp_path / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("FLASK", "DATABASE", "UV_"))
    }
    environment["PYTHONPATH"] = str(Path(__file__).parents[3])

    def run(*args, env=None):
        return subprocess.run(
            [sys.executable, "-m", "flask", *args],
            cwd=root,
            env=environment | (env or {}),
            capture_output=True,
            text=True,
            check=False,
        )

    return root, run


def test_prepare_creates_database_and_retains_records_and_credentials(preparation_app):
    root, run = preparation_app
    credentials = (root / "config/credentials.yml.enc").read_bytes()
    assert not (root / "storage/development.sqlite3").exists()
    result = run("db:prepare")
    assert result.returncode == 0, result.stderr
    assert (root / "storage/development.sqlite3").exists()
    result = run("generate", "model", "Post", "title:string")
    assert result.returncode == 0, result.stderr
    result = run("db:prepare")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(root / "storage/development.sqlite3") as database:
        database.execute("INSERT INTO posts (title) VALUES ('retained')")
    result = run("db:prepare")
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(root / "storage/development.sqlite3") as database:
        assert database.execute("SELECT title FROM posts").fetchall() == [("retained",)]
    assert (root / "config/credentials.yml.enc").read_bytes() == credentials


@pytest.mark.parametrize("environment", ["test", "production"])
def test_prepare_respects_environment_and_database_override(
    preparation_app, environment
):
    root, run = preparation_app
    env = {
        "FLASK_ENV": environment,
        "FLASKTEROIDS_MASTER_KEY": (root / "config/master.key").read_text().strip(),
    }
    result = run("db:prepare", env=env)
    assert result.returncode == 0, result.stderr
    assert (root / f"storage/{environment}.sqlite3").exists()
    env["DATABASE_URL"] = "sqlite:///storage/override.sqlite3"
    result = run("db:prepare", env=env)
    assert result.returncode == 0, result.stderr
    assert (root / "storage/override.sqlite3").exists()
    assert not (root / "storage/development.sqlite3").exists()


@pytest.mark.parametrize(
    "resource", ["alembic.ini", "env.py", "script.py.mako", "versions"]
)
def test_prepare_does_not_repair_missing_resources(preparation_app, resource):
    root, run = preparation_app
    path = root / "db/migrate" / resource
    if path.is_dir():
        (path / ".keep").unlink()
        path.rmdir()
    else:
        path.unlink()
    result = run("db:prepare")
    assert result.returncode != 0
    assert "Missing migration" in result.stderr
    assert not path.exists()
    with sqlite3.connect(root / "storage/development.sqlite3") as database:
        assert (
            database.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            == []
        )


def test_prepare_propagates_unknown_revision_and_bad_scripts(preparation_app):
    root, run = preparation_app
    assert run("db:prepare").returncode == 0
    with sqlite3.connect(root / "storage/development.sqlite3") as database:
        database.execute("INSERT INTO alembic_version VALUES ('unknown')")
    result = run("db:prepare")
    assert result.returncode != 0
    assert "unknown" in result.stderr
    with sqlite3.connect(root / "storage/development.sqlite3") as database:
        database.execute("DELETE FROM alembic_version")
    (root / "db/migrate/versions/broken.py").write_text("invalid python syntax !!!\n")
    result = run("db:prepare")
    assert result.returncode != 0
    assert "SyntaxError" in result.stderr


def test_prepare_does_not_create_arbitrary_database_directories(preparation_app):
    root, run = preparation_app
    result = run(
        "db:prepare", env={"DATABASE_URL": "sqlite:///absent/database.sqlite3"}
    )
    assert result.returncode != 0
    assert "unable to open database" in result.stderr
    assert not (root / "absent").exists()


def test_db_init_remains_strict(preparation_app):
    root, run = preparation_app
    original = (root / "db/migrate/env.py").read_bytes()
    result = run("db:init")
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert (root / "db/migrate/env.py").read_bytes() == original
