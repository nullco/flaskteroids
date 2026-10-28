import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from flaskteroids.cli.flaskteroids import cli
from tests.assertions import assert_pytest_passed

pytestmark = pytest.mark.generated_app


@pytest.fixture
def generated_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(args=["new", "uploads", "--skip-install"], standalone_mode=False)
    root = tmp_path / "uploads"
    environment = os.environ | {
        "PYTHONPATH": str(Path(__file__).parents[2]),
        "FLASKTEROIDS_ENV": "test",
    }

    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "flask", *args],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    return root, run


def test_storage_install_is_repeatable_and_migration_is_reversible(generated_app):
    root, run = generated_app
    original = (root / "config/storage.yml").read_text()
    run("attachments:install")
    assert "already exists" in run("attachments:install").stdout
    assert len(list((root / "db/migrate/versions").glob("*.py"))) == 1
    assert (root / "config/storage.yml").read_text() == original
    (root / "config/storage.yml").unlink()
    run("attachments:install")
    assert (root / "config/storage.yml").is_file()
    assert len(list((root / "db/migrate/versions").glob("*.py"))) == 1
    run("db:migrate")
    engine = create_engine(f"sqlite:///{root / 'storage/test.sqlite3'}")
    tables = inspect(engine).get_table_names()
    assert "attachment_blobs" in tables
    assert "record_attachments" in tables
    assert inspect(engine).get_indexes("record_attachments")[0]["unique"]
    run("db:rollback")
    assert "attachment_blobs" not in inspect(engine).get_table_names()
    engine.dispose()


def test_generated_attachment_scaffold_tests_pass(generated_app):
    root, run = generated_app
    run("attachments:install")
    run(
        "generate",
        "scaffold",
        "Member",
        "name:string",
        "avatar:attachment",
        "files:attachments",
    )
    model = (root / "app/models/member.py").read_text()
    assert "has_one_attached('avatar')" in model
    assert "has_many_attached('files')" in model
    report = root / "controller-tests.xml"
    run("test", "-q", "--junitxml", str(report), "test/controllers")
    assert_pytest_passed(report)


def test_authenticated_application_uploads_and_downloads_attachments(generated_app):
    root, run = generated_app
    run("attachments:install")
    run("generate", "authentication")
    run(
        "generate",
        "scaffold",
        "Member",
        "name:string",
        "avatar:attachment",
        "files:attachments",
    )
    source = Path(__file__).parent / "fixtures/attachments"
    shutil.copyfile(source / "member.py", root / "app/models/member.py")
    shutil.copyfile(source / "uploads.py", root / "test/controllers/uploads_test.py")
    report = root / "upload-tests.xml"
    run("test", "-q", "--junitxml", str(report), "test/controllers/uploads_test.py")
    assert_pytest_passed(report)
