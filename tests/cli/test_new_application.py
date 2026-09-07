import os
import subprocess
import sys
from flaskteroids.cli.flaskteroids import cli


def test_generated_application_boots_in_development_and_production(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    result = cli.main(
        args=["new", "weblog"],
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
    )
    assert development.returncode == 0, development.stderr

    environment = os.environ | {
        "FLASKTEROIDS_ENV": "production",
        "FLASKTEROIDS_MASTER_KEY": (root / "config" / "master.key")
        .read_text()
        .strip(),
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
    )
    assert production.returncode == 0, production.stderr
