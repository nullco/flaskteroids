"""The same generated-application scenarios run against every database backend."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


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
        PYTHONPATH=str(Path(__file__).parents[2]),
        DATABASE_URL=os.environ.get("DATABASE_URL", "sqlite:///storage/test.sqlite3"),
    )

    def run(*args, code=None):
        command = (
            [sys.executable, "-c", code]
            if code is not None
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


def test_normal_boot_uses_database_configuration_and_keeps_unused_models_lazy(
    generated_application,
):
    _, run = generated_application
    run(
        code="""
import os
import pytest
from sqlalchemy.engine import make_url
from wsgi import app
from app.models.deferred_record import DeferredRecord
from flaskteroids.exceptions import ProgrammerError

assert app.env.test
assert make_url(app.database_url) == make_url(os.environ['DATABASE_URL'])
with app.app_context():
    assert app.make_shell_context()['DeferredRecord'] is DeferredRecord
    with pytest.raises(ProgrammerError, match='DeferredRecord.*migrations'):
        DeferredRecord.first()
assert app.test_client().get('/up/').status_code == 200
"""
    )


def test_generated_controller_model_and_mailer_suites(generated_application):
    _, run = generated_application
    result = run(
        "test", "-q", "--tb=short", "test/controllers", "test/models", "test/mailers"
    )
    assert "passed" in result.stdout
    assert "skipped" not in result.stdout


def test_repeated_preparation_preserves_records_and_credentials(generated_application):
    root, run = generated_application
    credentials = (root / "config/credentials.yml.enc").read_bytes()
    run(
        code="""
from wsgi import app
from app.models.post import Post
with app.app_context():
    post = Post.create(title='retained', content='original')
    assert post.id
"""
    )
    run("db:create")
    run("db:prepare")
    run("db:prepare")
    run(
        code="""
from wsgi import app
from app.models.post import Post
with app.app_context():
    post = Post.find_by(title='retained')
    assert post.content == 'original'
    assert post.update(content='updated')
    assert post.reload().content == 'updated'
"""
    )
    assert (root / "config/credentials.yml.enc").read_bytes() == credentials


def test_generated_migrations_apply_and_rollback_in_fresh_applications(
    generated_application,
):
    root, run = generated_application
    versions = root / "db/migrate/versions"
    before = set(versions.glob("*.py"))
    run("generate", "migration", "AddPublishedToPosts", "published:boolean")
    run("db:migrate")
    run(
        code="""
from wsgi import app
from app.models.post import Post
with app.app_context():
    assert 'published' in Post.new().column_names
"""
    )
    run("db:rollback")
    run(
        code="""
from wsgi import app
from app.models.post import Post
with app.app_context():
    assert 'published' not in Post.new().column_names
"""
    )
    for migration in set(versions.glob("*.py")) - before:
        migration.unlink()
