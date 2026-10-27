import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from flaskteroids.cli.flaskteroids import cli


@pytest.fixture(scope="module")
def generated_app_factory(tmp_path_factory):
    def create(name, *options):
        root = tmp_path_factory.mktemp("application") / name
        result = CliRunner().invoke(cli, ["new", str(root), "--skip-install", *options])
        assert result.exit_code == 0, result.output
        (root / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("FLASK", "UV_"))
        }
        environment.update(
            FLASKTEROIDS_ENV="test",
            PYTHONPATH=os.pathsep.join((str(root), str(Path(__file__).parents[1]))),
            FLASKTEROIDS_DATABASE_URL=os.environ.get(
                "FLASKTEROIDS_DATABASE_URL", "sqlite:///storage/test.sqlite3"
            ),
        )

        def run(*args, script=None):
            command = (
                [
                    sys.executable,
                    str(Path(__file__).parent / "integration/scenarios" / script),
                    *args,
                ]
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

        return root, run

    return create


@pytest.fixture(scope="module")
def generated_scaffolds(generated_app_factory):
    root, run = generated_app_factory("catalog")
    scaffolds = {
        "Post": ("title:string", "content:text"),
        "Fish": ("name:string",),
        "Equipment": ("name:string",),
    }
    run("db:create")
    for model, fields in scaffolds.items():
        run("generate", "scaffold", model, *fields)
    run("db:prepare")
    try:
        yield root, run
    finally:
        for _ in scaffolds:
            run("db:rollback")


@pytest.fixture(scope="module")
def generated_api(generated_app_factory):
    root, run = generated_app_factory("inventory", "--api")
    run("db:create")
    for name, fields in (
        (
            "Post",
            (
                "title:string",
                "content:text",
                "published:boolean",
                "quantity:integer",
                "published_at:datetime",
                "settings:json",
            ),
        ),
        ("Fish", ("name:string",)),
        ("Equipment", ("name:string",)),
        ("Document", ("name:string", "file:attachment")),
        ("Empty", ()),
    ):
        run("generate", "scaffold", name, *fields)
    run("attachments:install")
    run("generate", "controller", "Status", "index")
    run("generate", "resource", "Widget", "name:string")
    run("generate", "mailer", "Notifications", "welcome")
    source = Path(__file__).parent / "integration/application/api"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            destination = root / path.relative_to(source)
            if path.name == "contracts.py":
                destination = destination.with_name("api_contract_test.py")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    run("db:prepare")
    return root, run


@pytest.fixture(scope="module")
def generated_store(generated_app_factory):
    root, run = generated_app_factory("store")
    run("db:create")
    run("generate", "scaffold", "Product", "name:string", "quantity:integer")
    run("generate", "model", "Subscriber", "product:references", "email:string")
    run("generate", "authentication")
    source = Path(__file__).parent / "integration/application/store"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            destination = root / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    run("db:prepare")
    migrations = list((root / "db/migrate/versions").glob("*.py"))
    try:
        yield root, run
    finally:
        for _ in migrations:
            run("db:rollback")
