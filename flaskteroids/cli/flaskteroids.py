import json
import os
import re
import secrets
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import click
import yaml
from alembic.util import CommandError
from packaging.version import InvalidVersion, Version

from flaskteroids.cli.agent_skills import agent_skills
from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException
from flaskteroids.cli.attachments import STORAGE_YAML
from flaskteroids.cli.db.config import initialize_migrations
from flaskteroids.cli.generators.templates import template
from flaskteroids.credentials import encrypt, generate_key


@click.group()
def cli():
    """Create applications and locate agent skills.

    For application commands, run bin/flask --help from the application root.
    Use COMMAND --help for usage and examples.
    """


cli.add_command(agent_skills)


@cli.command("new")
@click.argument("app_name")
@click.option(
    "--skip-install",
    is_flag=True,
    help="Skip dependency installation and database preparation; run bin/setup later.",
)
def new(app_name, skip_install):
    """Create a ready-to-run application.

    Creates the APP_NAME directory with tests, encrypted credentials, Docker
    support, and version-matched agent guidance. Installs dependencies with uv
    and prepares the selected database (development by default). Requires Git
    and Bash/POSIX scripts; uv is required unless --skip-install is used.
    Use a new directory: existing files may be overwritten.

    \b
    Example:
      flaskteroids new my_app
    """
    base_path = os.path.abspath(app_name)
    project_name = Path(base_path).name
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", project_name):
        raise click.BadParameter(
            "destination basename must be a valid Python project name",
            param_hint="APP_NAME",
        )
    try:
        installed = Version(version("flaskteroids"))
    except (PackageNotFoundError, InvalidVersion) as error:
        raise click.ClickException(
            f"Cannot determine installed Flaskteroids version: {error}"
        ) from error
    # The app owns its resolution/lock. Unpublished generators need an explicit source.
    epoch = f"{installed.epoch}!" if installed.epoch else ""
    constraint = (
        f"=={installed}"
        if installed.is_prerelease or installed.is_devrelease or installed.local
        else f">={installed},<{epoch}{installed.major}.{installed.minor + 1}.0"
    )
    params = {
        "project_title": project_name.replace("_", " ").title(),
        "project_name_toml": json.dumps(project_name),
        "framework_dependency_toml": json.dumps(f"flaskteroids{constraint}"),
    }
    ab = ArtifactsBuilder(base_path, click.echo)
    try:
        ab.dir()
        ab.file("README.md", _template(path="README.md.mako", params=params))
        ab.file(
            ".agents/skills/using-flaskteroids/SKILL.md",
            _template(path="agent_skill.md.mako"),
        )
        ab.file("Dockerfile", _template(path="Dockerfile.mako"))
        ab.file(".dockerignore", _template(path="dockerignore.mako"))
        ab.file(".gitignore", _template(path="gitignore.mako"))
        ab.file("pyproject.toml", _template(path="pyproject.toml.mako", params=params))
        ab.file("config/application.py", _template(path="config/application.py.mako"))
        ab.file("config/boot.py", _template(path="config/boot.py.mako"))
        ab.file("config/environment.py", _template(path="config/environment.py.mako"))
        for environment in ("development", "test", "production"):
            ab.file(
                f"config/environments/{environment}.py",
                _template(path=f"config/environments/{environment}.py.mako"),
            )
        ab.file("config/initializers/.keep")
        ab.file("config/database.yml", _template(path="config/database.yml.mako"))
        ab.file("config/storage.yml", STORAGE_YAML)
        credentials_key = generate_key()
        credentials = yaml.safe_dump(
            {"secret_key_base": secrets.token_hex(64)}, sort_keys=False
        )
        ab.file("config/master.key", f"{credentials_key}\n")
        ab.file("config/credentials.yml.enc", encrypt(credentials, credentials_key))
        ab.file("wsgi.py", _template(path="wsgi.py.mako"))
        ab.file("jobs.py", _template(path="jobs.py.mako"))
        ab.file("bin/flask", _template(path="bin/flask.mako"))
        ab.file("bin/setup", _template(path="bin/setup.mako"))
        ab.file("bin/release", _template(path="bin/release.mako"))
        ab.file("bin/docker-entrypoint", _template(path="bin/docker-entrypoint.mako"))
        ab.file("Procfile", _template(path="Procfile.mako"))
        ab.file("deploy/README.md", _template(path="deploy/README.md.mako"))
        ab.file("storage/.keep")
        ab.dir("db/")
        ab.dir("app/")
        ab.file("app/assets/stylesheets/application.css")
        ab.file("app/assets/images/.keep")
        ab.file(
            "app/helpers/application_helper.py",
            _template(path="app/helpers/application_helper.py.mako"),
        )
        ab.file(
            "app/models/application_model.py",
            _template(path="app/models/application_model.py.mako"),
        )
        ab.file("app/jobs/application_job.py")
        ab.file(
            "app/mailers/application_mailer.py",
            _template(path="app/mailers/application_mailer.py.mako"),
        )
        ab.file(
            "app/views/layouts/application.html",
            _template(path="app/views/layouts/application.html.mako"),
        )
        ab.file("app/views/layouts/mailer.html")
        ab.file("app/views/layouts/mailer.txt")
        ab.file(
            "app/controllers/application_controller.py",
            _template(path="app/controllers/application_controller.py.mako"),
        )
        ab.file(
            "config/routes.py",
            'def register(route):\n    route.get("/up/", to="flaskteroids/health#show")\n',
        )
        ab.file("test/__init__.py")
        ab.file("test/conftest.py", _template(path="test/conftest.py.mako"))
        ab.file("test/test_helper.py", _template(path="test/test_helper.py.mako"))
        ab.file(
            "test/controllers/health_controller_test.py",
            _template(path="test/controllers/health_controller_test.py.mako"),
        )
        for directory in (
            "fixtures",
            "models",
            "controllers",
            "mailers",
            "jobs",
            "system",
        ):
            ab.file(f"test/{directory}/.keep")
        ab.file(
            ".github/workflows/test.yml",
            _template(path=".github/workflows/test.yml.mako"),
        )
        # Copy canonical Alembic assets before app dependencies or database are available.
        initialize_migrations(Path(base_path) / "db/migrate")
        ab.file("db/migrate/versions/.keep")
        try:
            ab.run("git init")
            ab.run("git branch -m main")
        except FileNotFoundError as error:
            raise click.ClickException(
                "Git is required to create an application; install Git and retry."
            ) from error
        if not skip_install:
            # Relative argv uses the builder's app cwd, including destinations with spaces.
            ab.run("bin/setup")
    except (ArtifactsBuilderException, CommandError) as error:
        raise click.ClickException(
            f"Error creating new Flaskteroids app: {error}"
        ) from error
    if skip_install:
        click.echo(
            "Application generated; installation and database preparation skipped. Run bin/setup."
        )
    else:
        click.echo(
            "Application ready. Run bin/flask run, bin/flask test, and bin/flask test:system."
        )
    click.echo(f"Next: cd {app_name!r}")


def _template(*, path, params=None):
    return template("flaskteroids.cli", path=path, params=params)
