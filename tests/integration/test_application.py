"""The same generated-application scenarios run against every database backend."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli
from tests.assertions import assert_pytest_passed


@pytest.fixture(scope="module")
def generated_application(tmp_path_factory):
    root = tmp_path_factory.mktemp("application") / "weblog"
    result = CliRunner().invoke(cli, ["new", str(root), "--skip-install"])
    assert result.exit_code == 0, result.output
    (root / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("FLASK", "UV_"))
    }
    environment.update(
        FLASK_ENV="test",
        PYTHONPATH=os.pathsep.join((str(root), str(Path(__file__).parents[2]))),
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///storage/test.sqlite3"),
    )

    def run(*args, script=None):
        command = (
            [sys.executable, str(Path(__file__).parent / "scenarios" / script)]
            if script is not None
            else [str(root / "bin/flask"), *args]
        )
        result = subprocess.run(
            command,
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    (root / "app/models/deferred_record.py").write_text(
        "from app.models.application_model import ApplicationModel\n"
        "class DeferredRecord(ApplicationModel):\n    pass\n"
    )
    run("db:create", "--help")
    run("db:create")
    run("generate", "scaffold", "Post", "title:string", "content:text")
    run("generate", "model", "Writer", "name:string")
    run("generate", "model", "Story", "title:string", "writer:references")
    run("generate", "mailer", "Notices", "welcome")
    source = Path(__file__).parent / "application"
    for name in ("writer.py", "story.py"):
        shutil.copyfile(source / name, root / "app/models" / name)
    shutil.copyfile(source / "contracts.py", root / "test/models/contracts_test.py")
    (root / "test/fixtures/writers.yml").write_text("one:\n  name: fixture writer\n")
    (root / "test/fixtures/stories.yml").write_text(
        "one:\n  title: fixture story\n  writer: one\n"
    )
    run("db:prepare")
    migrations = list((root / "db/migrate/versions").glob("*.py"))
    try:
        yield root, run
    finally:
        for _ in migrations:
            run("db:rollback")


def test_normal_boot_declares_models_without_requiring_unmigrated_snapshots(
    generated_application,
):
    _, run = generated_application
    run(script="boot.py")


def test_generated_controller_model_and_mailer_suites_pass(generated_application):
    root, run = generated_application
    report = root / "generated-tests.xml"
    run(
        "test",
        "-q",
        "--junitxml",
        str(report),
        "test/controllers",
        "test/models",
        "test/mailers",
    )
    assert_pytest_passed(report)


def test_repeated_preparation_preserves_records_and_credentials(generated_application):
    root, run = generated_application
    credentials = (root / "config/credentials.yml.enc").read_bytes()
    run(script="create_retained_record.py")
    run("db:create")
    run("db:prepare")
    run("db:prepare")
    run(script="update_retained_record.py")
    assert (root / "config/credentials.yml.enc").read_bytes() == credentials


def test_standalone_saves_commit_and_explicit_transactions_control_rollback(
    generated_application,
):
    _, run = generated_application
    run(script="transactions.py")


def test_generated_migrations_apply_and_rollback_in_fresh_applications(
    generated_application,
):
    root, run = generated_application
    versions = root / "db/migrate/versions"
    before = set(versions.glob("*.py"))
    run("generate", "migration", "AddPublishedToPosts", "published:boolean")
    schema_path = root / "db/schema.py"
    original_schema = schema_path.read_bytes()
    run("db:migrate")
    assert schema_path.read_bytes() != original_schema
    run(script="migrated_columns.py")
    run("db:rollback")
    assert schema_path.read_bytes() == original_schema
    run(script="rolled_back_columns.py")
    for migration in set(versions.glob("*.py")) - before:
        migration.unlink()
