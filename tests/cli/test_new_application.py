import os
import shutil
import subprocess
import sys
from pathlib import Path

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


def test_generated_scaffold_controller_tests_pass(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(
        args=["new", "weblog"],
        prog_name="flaskteroids",
        standalone_mode=False,
    )
    root = tmp_path / "weblog"
    environment = os.environ | {"PYTHONPATH": str(Path(__file__).parents[2])}
    if chrome := shutil.which("google-chrome"):
        environment["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = chrome

    scaffold = subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "generate",
            "scaffold",
            "Post",
            "title:string",
            "content:text",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert scaffold.returncode == 0, scaffold.stderr

    mailer = subprocess.run(
        [sys.executable, "-m", "flask", "generate", "mailer", "User", "welcome"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert mailer.returncode == 0, mailer.stderr

    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "flaskteroids",
            "test",
            "-q",
            "test/controllers",
            "test/mailers",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert tests.returncode == 0, tests.stdout + tests.stderr
    assert "8 passed" in tests.stdout

    system_tests = subprocess.run(
        [sys.executable, "-m", "flaskteroids", "test:system", "-q"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert system_tests.returncode == 0, system_tests.stdout + system_tests.stderr
    assert "1 passed" in system_tests.stdout
