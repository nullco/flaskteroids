import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from flaskteroids.cli.flaskteroids import cli


@pytest.fixture
def generated_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(args=["new", "uploads"], standalone_mode=False)
    root = tmp_path / "uploads"
    environment = os.environ | {
        "PYTHONPATH": str(Path(__file__).parents[2]),
        "FLASK_ENV": "test",
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
    assert "7 passed" in run("test", "-q", "test/controllers").stdout


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
    model_path = root / "app/models/member.py"
    model_path.write_text(
        "from flaskteroids.callbacks import after_commit\n"
        + model_path.read_text().replace(
            "has_many_attached('files')",
            "has_many_attached('files'), after_commit('verify_committed_upload')",
        )
        + "\n    def verify_committed_upload(self):\n        assert self.avatar.download().strip() == b'An example attachment.'\n"
    )
    (
        root / "test/controllers/uploads_test.py"
    ).write_text("""from flaskteroids.callbacks import after_commit
from flask import current_app, session as browser_session
from flaskteroids.testing.context import current_response
from test.test_helper import IntegrationTest, fixture_file_upload, get, post
from app.models.member import Member
from app.models.session import Session
from app.models.user import User
from flaskteroids.attachments import blob_path


class UploadsTest(IntegrationTest):
    def test_authenticated_upload(self):
        user = User.create(email_address="owner@example.com", password="password")
        post("/session/", params={"email_address": user.email_address, "password": "password"})
        self.assert_response("redirect")
        get("/members/new/")
        self.assert_response("success")
        assert 'enctype="multipart/form-data"' in current_response().text
        post("/members/", params={"member": {
            "name": "Owner",
            "avatar": fixture_file_upload("attachment.txt"),
            "files": [fixture_file_upload("attachment.txt"), fixture_file_upload("attachment.txt")],
        }})
        self.assert_response("redirect")
        member = Member.last()
        assert member.avatar.attached()
        assert len(member.files) == 2
        assert member.avatar.download() == b"An example attachment.\\n"
        with current_app.test_request_context():
            url = blob_path(member.avatar)
        get(url)
        self.assert_response("redirect")
        current_app.config.attachments.authorize = lambda blob: False
        get(url)
        self.assert_response("missing")
        current_app.config.attachments.authorize = lambda blob: bool(
            Session.find_by(id=browser_session.get("session_id"))
        )
        get(url, follow_redirects=True)
        self.assert_response("success")
        assert current_response().data == member.avatar.download()
""")
    assert "1 passed" in run("test", "-q", "test/controllers/uploads_test.py").stdout
