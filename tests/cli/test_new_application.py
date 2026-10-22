import os
import subprocess
import sys
from pathlib import Path

from flaskteroids.cli.flaskteroids import cli


def test_generated_application_boots_in_development_and_production(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    result = cli.main(
        args=["new", "weblog", "--skip-install"],
        prog_name="flaskteroids",
        standalone_mode=False,
    )
    assert result is None

    root = tmp_path / "weblog"
    development = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from wsgi import app; "
                "assert app.env.development; "
                "assert app.database_url == "
                "'sqlite:///storage/development.sqlite3'"
            ),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert development.returncode == 0, development.stderr

    environment = os.environ | {
        "FLASK_ENV": "production",
        "FLASKTEROIDS_MASTER_KEY": (root / "config" / "master.key").read_text().strip(),
        "DATABASE_URL": "sqlite:///:memory:",
    }
    production = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from wsgi import app; "
                "assert app.env.production; "
                "assert app.database_url == 'sqlite:///:memory:'; "
                "assert app.secret_key"
            ),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert production.returncode == 0, production.stderr


def test_generated_model_can_boot_migrate_and_use_fresh_mappings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(
        args=["new", "weblog", "--skip-install"],
        prog_name="flaskteroids",
        standalone_mode=False,
    )
    root = tmp_path / "weblog"
    environment = os.environ | {
        "PYTHONPATH": os.pathsep.join((str(root), str(Path(__file__).parents[2]))),
        "FLASK_ENV": "development",
    }

    def run(*args):
        return subprocess.run(
            [sys.executable, *args],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    generated = run("-m", "flask", "generate", "model", "Post", "title:string")
    assert generated.returncode == 0, generated.stdout + generated.stderr

    boot = run("-c", "from wsgi import app; assert app.env.development")
    assert boot.returncode == 0, boot.stderr

    unbacked = run(
        "-c",
        """
from unittest.mock import patch
with patch('sqlalchemy.engine.Engine.connect', side_effect=AssertionError('unexpected connection')):
    from wsgi import app
    from app.models.post import Post
    assert '__mapper__' not in vars(Post)
""",
    )
    assert unbacked.returncode == 0, unbacked.stderr
    query = run(
        "-c",
        "from wsgi import app; from app.models.post import Post; "
        "ctx = app.app_context(); ctx.push(); Post.first()",
    )
    assert query.returncode != 0
    assert "ProgrammerError" in query.stderr
    assert "posts" in query.stderr
    assert "migrations" in query.stderr

    help_result = run("-m", "flask", "db:migrate", "--help")
    assert help_result.returncode == 0, help_result.stderr
    migrated = run("-m", "flask", "db:migrate")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    assert "posts" in (root / "db/schema.py").read_text()
    assert not (root / "app/schema.py").exists()

    fresh = run(str(Path(__file__).parent / "fixtures/application/fresh_records.py"))
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
