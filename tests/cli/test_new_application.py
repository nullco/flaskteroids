import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from flaskteroids.cli.flaskteroids import cli


def test_generated_application_declares_runtime_dependencies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(
        args=["new", "weblog"],
        prog_name="flaskteroids",
        standalone_mode=False,
    )

    generated = tomllib.loads((tmp_path / "weblog" / "pyproject.toml").read_text())

    assert generated["project"]["dependencies"] == ["flaskteroids", "gunicorn"]
    assert "dependency-groups" not in generated

    dockerfile = (tmp_path / "weblog" / "Dockerfile").read_text()
    assert (
        "RUN pip install --no-cache-dir -r /requirements.txt flaskteroids\n"
        in dockerfile
    )
    assert 'CMD ["gunicorn", "wsgi:app"' in dockerfile


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
    cli.main(args=["new", "weblog"], prog_name="flaskteroids", standalone_mode=False)
    root = tmp_path / "weblog"
    environment = os.environ | {
        "PYTHONPATH": str(Path(__file__).parents[2]),
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
from wsgi import app
from app.models.post import Post
with app.app_context():
    Post.new(title="not-in-error-message")
""",
    )
    assert unbacked.returncode != 0
    for fragment in ("ProgrammerError", "Post", "posts", "migrations", "fresh"):
        assert fragment in unbacked.stderr
    # Tracebacks show source lines, so inspect only the exception message for values.
    assert "not-in-error-message" not in unbacked.stderr.split("ProgrammerError:")[-1]

    help_result = run("-m", "flask", "db:migrate", "--help")
    assert help_result.returncode == 0, help_result.stderr
    migrated = run("-m", "flask", "db:migrate")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr

    fresh = run(
        "-c",
        """
from wsgi import app
from app.models.post import Post
with app.app_context():
    post = Post.create(title="first")
    assert post.id
    assert Post.find(post.id).title == "first"
    assert post.update(title="second")
    assert post.reload().title == "second"
    assert Post.where(title="second").count() == 1
""",
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr


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
        check=False,
    )
    assert scaffold.returncode == 0, scaffold.stderr

    mailer = subprocess.run(
        [sys.executable, "-m", "flask", "generate", "mailer", "User", "welcome"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert mailer.returncode == 0, mailer.stderr

    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "flask",
            "test",
            "-q",
            "test/controllers",
            "test/mailers",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tests.returncode == 0, tests.stdout + tests.stderr
    assert "8 passed" in tests.stdout

    system_tests = subprocess.run(
        [sys.executable, "-m", "flask", "test:system", "-q"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert system_tests.returncode == 0, system_tests.stdout + system_tests.stderr
    assert "1 passed" in system_tests.stdout
