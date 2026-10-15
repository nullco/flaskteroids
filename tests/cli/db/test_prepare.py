import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


def write_post_declaration(root):
    (root / "app/models/post.py").write_text(
        "from app.models.application_model import ApplicationModel\n"
        "class Post(ApplicationModel):\n    pass\n"
    )


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

    def run(*args, env=None, launcher=None, cwd=None):
        return subprocess.run(
            [*(launcher or [sys.executable, "-m", "flask"]), *args],
            cwd=cwd or root,
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
    assert not (root / "storage/development.sqlite3").exists()


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
    assert "SQLite database ensure/connection failed" in result.stderr
    assert "parent directory exists" in result.stderr
    assert not (root / "absent").exists()


def test_db_init_remains_strict(preparation_app):
    root, run = preparation_app
    original = (root / "db/migrate/env.py").read_bytes()
    result = run("db:init")
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert (root / "db/migrate/env.py").read_bytes() == original


def test_init_is_registration_only_and_does_not_connect(preparation_app):
    root, run = preparation_app
    write_post_declaration(root)
    (root / "app/schema.py").unlink()
    shutil.rmtree(root / "db/migrate")
    result = run("db:init")
    assert result.returncode == 0, result.stderr
    assert (root / "db/migrate/env.py").exists()
    assert not (root / "storage/development.sqlite3").exists()


def test_migration_execution_failure_keeps_database_and_uses_safe_errors(
    preparation_app,
):
    root, run = preparation_app
    (root / "db/migrate/versions/a.py").write_text(
        "from alembic import op\nrevision = 'a'\ndown_revision = None\n"
        "def upgrade():\n    op.execute('SELECT * FROM private_driver_message')\n"
        "def downgrade():\n    pass\n"
    )
    result = run("db:prepare")
    assert result.returncode != 0
    assert "SQLite migration failed" in result.stderr
    assert "left in place for diagnosis" in result.stderr
    assert "sqlite3.OperationalError" not in result.stderr
    assert "private_driver_message" not in result.stderr
    assert (root / "storage/development.sqlite3").exists()


def test_help_still_validates_production_credentials(preparation_app):
    root, run = preparation_app
    (root / "config/master.key").unlink()
    result = run("db:create", "--help", env={"FLASK_ENV": "production"})
    assert result.returncode != 0
    assert "Missing credentials key" in result.stderr
    assert not (root / "storage/production.sqlite3").exists()


def test_create_requires_no_migrations_and_does_not_create_tables(preparation_app):
    root, run = preparation_app
    shutil.rmtree(root / "db/migrate")
    for _ in range(2):
        result = run("db:create")
        assert result.returncode == 0, result.stderr
    with sqlite3.connect(root / "storage/development.sqlite3") as database:
        assert (
            database.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            == []
        )


@pytest.mark.parametrize("graph", ["broken", "missing", "cycle", "heads"])
def test_prepare_preflights_before_provisioning_or_executing_env(
    preparation_app, graph
):
    root, run = preparation_app
    versions = root / "db/migrate/versions"
    if graph == "broken":
        (versions / "a.py").write_text("broken python !!!\n")
    else:
        down = {"missing": "absent", "cycle": "a", "heads": None}[graph]
        (versions / "a.py").write_text(f"revision = 'a'\ndown_revision = {down!r}\n")
        if graph == "heads":
            (versions / "b.py").write_text("revision = 'b'\ndown_revision = None\n")
    (root / "db/migrate/env.py").write_text(
        "raise RuntimeError('env.py was executed')\n"
    )
    result = run("db:prepare")
    assert result.returncode != 0
    assert "env.py was executed" not in result.stderr
    assert not (root / "storage/development.sqlite3").exists()


@pytest.mark.parametrize("launcher", ["bin", "flask", "python", "uv"])
def test_normal_flask_launchers_help_and_preparation(preparation_app, launcher):
    root, run = preparation_app
    (root / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
    write_post_declaration(root)
    launchers = {
        "bin": [str(root / "bin/flask")],
        "flask": [str(Path(sys.prefix) / "bin/flask")],
        "python": [sys.executable, "-m", "flask"],
        "uv": [shutil.which("uv"), "run", "flask"],
    }
    prefix = launchers[launcher]
    env = {"UV_NO_SYNC": "1", "FLASK_APP": "wsgi:app"}
    result = run("--app", "wsgi:app", "db:create", "--help", launcher=prefix, env=env)
    assert result.returncode == 0, result.stderr
    assert not (root / "storage/development.sqlite3").exists()
    result = run("db:prepare", launcher=prefix, env=env)
    assert result.returncode == 0, result.stderr
    assert (root / "storage/development.sqlite3").exists()


def test_custom_factory_and_project_root_migrations_work_from_another_cwd(
    preparation_app,
):
    root, run = preparation_app
    url = f"sqlite:///{root / 'storage/selected.sqlite3'}"
    (root / "config/database.yml").write_text(f"development:\n  url: {url!r}\n")
    (root / "selection.py").write_text(
        "from config.application import Application\n"
        "from pathlib import Path\n"
        "def create_app():\n"
        "    return Application.initialize(root_path=Path(__file__).parent)\n"
    )
    result = run(
        "--app",
        "selection:create_app",
        "db:prepare",
        cwd=root.parent,
        env={"PYTHONPATH": str(root) + os.pathsep + str(Path(__file__).parents[3])},
    )
    assert result.returncode == 0, result.stderr
    assert (root / "storage/selected.sqlite3").exists()
    assert not (root / "storage/development.sqlite3").exists()


def test_percent_in_database_filename_survives_alembic_interpolation(preparation_app):
    root, run = preparation_app
    result = run(
        "db:prepare", env={"DATABASE_URL": "sqlite:///storage/100%ready.sqlite3"}
    )
    assert result.returncode == 0, result.stderr
    assert (root / "storage/100%ready.sqlite3").exists()


def test_dotenv_selection_and_global_options_use_normal_flask_discovery(
    preparation_app,
):
    root, run = preparation_app
    (root / ".env").write_text("DATABASE_URL=sqlite:///storage/dotenv.sqlite3\n")
    (root / ".flaskenv").write_text("FLASK_APP=wsgi:app\n")
    result = run("--env-file", str(root / ".env"), "db:prepare")
    assert result.returncode == 0, result.stderr
    assert (root / "storage/dotenv.sqlite3").exists()


def test_startup_queries_are_not_skipped_for_database_commands(preparation_app):
    root, run = preparation_app
    write_post_declaration(root)
    (root / "config/initializers/query.py").write_text(
        "from app.models.post import Post\nPost.first()\n"
    )
    result = run("db:create")
    assert result.returncode != 0
    assert "ProgrammerError" in result.stderr
    assert "posts" in result.stderr
    assert "migrations" in result.stderr
    assert not (root / "storage/development.sqlite3").exists()
