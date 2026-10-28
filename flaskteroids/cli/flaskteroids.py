import json
import os
import re
import secrets
from importlib.metadata import PackageNotFoundError, distribution, version
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

import click
import yaml
from alembic.util import CommandError
from packaging.version import InvalidVersion, Version

from flaskteroids.cli.agent_skills import agent_skills
from flaskteroids.cli.application import application_generator
from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException
from flaskteroids.cli.assets import precompile as assets_precompile
from flaskteroids.cli.attachments import STORAGE_YAML
from flaskteroids.cli.db.config import initialize_migrations
from flaskteroids.cli.importmap import importmap
from flaskteroids.credentials import encrypt, generate_key


@click.group()
def cli():
    """Create applications, compile assets, and locate agent skills.

    For application commands, run bin/flask --help from the application root.
    Use COMMAND --help for usage and examples.
    """


cli.add_command(agent_skills)
cli.add_command(assets_precompile)
cli.add_command(importmap)


@cli.command("new")
@click.argument("app_name")
@click.option(
    "--skip-install",
    is_flag=True,
    help="Skip dependency installation and database preparation; run bin/setup later.",
)
@click.option(
    "--api", "api_only", is_flag=True, help="Generate an API-only application."
)
def new(app_name, skip_install, api_only):
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
        editable_path = _editable_framework_path()
    except (PackageNotFoundError, InvalidVersion) as error:
        raise click.ClickException(
            f"Cannot determine installed Flaskteroids version: {error}"
        ) from error
    # The app owns its resolution/lock, preserving editable generators as local sources.
    constraint = (
        f"=={installed}"
        if installed.is_prerelease or installed.is_devrelease or installed.local
        else f">={installed}"
    )
    params = {
        "project_title": project_name.replace("_", " ").title(),
        "browser_dependencies": [] if api_only else ["flaskteroids-turbo>=0.1.0,<0.2"],
        "project_name_toml": json.dumps(project_name),
        "framework_dependency_toml": json.dumps(f"flaskteroids{constraint}"),
        "framework_path_toml": json.dumps(str(editable_path))
        if editable_path
        else None,
    }
    generator = application_generator(api_only, params)
    ab = ArtifactsBuilder(base_path, click.echo)
    try:
        ab.dir()
        ab.file("README.md", generator.render(path="README.md.mako", params=params))
        ab.file(
            ".agents/skills/using-flaskteroids/SKILL.md",
            generator.render(path="agent_skill.md.mako"),
        )
        ab.file("Dockerfile", generator.render(path="Dockerfile.mako", params=params))
        ab.file(".dockerignore", generator.render(path="dockerignore.mako"))
        ab.file(".gitignore", generator.render(path="gitignore.mako"))
        ab.file(
            "pyproject.toml",
            generator.render(path="pyproject.toml.mako", params=params),
        )
        ab.file(
            "config/application.py",
            generator.render(path="config/application.py.mako", params=params),
        )
        ab.file("config/boot.py", generator.render(path="config/boot.py.mako"))
        ab.file(
            "config/environment.py", generator.render(path="config/environment.py.mako")
        )
        for environment in ("development", "test", "production"):
            ab.file(
                f"config/environments/{environment}.py",
                generator.render(path=f"config/environments/{environment}.py.mako"),
            )
        ab.file("config/initializers/.keep")
        ab.file(
            "config/database.yml", generator.render(path="config/database.yml.mako")
        )
        ab.file("config/storage.yml", STORAGE_YAML)
        ab.file("config/locales/en.yml", 'en:\n  hello: "Hello world"\n')
        credentials_key = generate_key()
        credentials = yaml.safe_dump(
            {"secret_key_base": secrets.token_hex(64)}, sort_keys=False
        )
        ab.file("config/master.key", f"{credentials_key}\n")
        ab.file("config/credentials.yml.enc", encrypt(credentials, credentials_key))
        ab.file("wsgi.py", generator.render(path="wsgi.py.mako"))
        ab.file("jobs.py", generator.render(path="jobs.py.mako"))
        ab.file("bin/flask", generator.render(path="bin/flask.mako"))
        ab.file("bin/jobs", generator.render(path="bin/jobs.mako"))
        ab.file("bin/setup", generator.render(path="bin/setup.mako"))
        ab.file("bin/release", generator.render(path="bin/release.mako"))
        ab.file(
            "bin/docker-entrypoint", generator.render(path="bin/docker-entrypoint.mako")
        )
        ab.file("Procfile", generator.render(path="Procfile.mako"))
        ab.file(
            "deploy/README.md",
            generator.render(path="deploy/README.md.mako", params=params),
        )
        ab.file("storage/.keep")
        ab.dir("db/")
        ab.dir("app/")
        generator.write_presentation(ab)
        ab.file(
            "app/models/application_model.py",
            generator.render(path="app/models/application_model.py.mako"),
        )
        ab.file("db/schema.py", generator.render(path="db/schema.py.mako"))
        ab.file("app/jobs/application_job.py")
        ab.file(
            "app/mailers/application_mailer.py",
            generator.render(path="app/mailers/application_mailer.py.mako"),
        )
        ab.file("app/views/layouts/mailer.html")
        ab.file("app/views/layouts/mailer.txt")
        ab.file(
            "app/controllers/application_controller.py",
            generator.render(
                path="app/controllers/application_controller.py.mako", params=params
            ),
        )
        ab.file(
            "config/routes.py",
            'def register(route):\n    route.get("/up/", to="flaskteroids/health#show")\n',
        )
        ab.file("test/__init__.py")
        ab.file("test/conftest.py", generator.render(path="test/conftest.py.mako"))
        ab.file(
            "test/test_helper.py",
            generator.render(path="test/test_helper.py.mako", params=params),
        )
        ab.file(
            "test/controllers/health_controller_test.py",
            generator.render(path="test/controllers/health_controller_test.py.mako"),
        )
        for directory in generator.test_directories:
            ab.file(f"test/{directory}/.keep")
            if directory != "fixtures":
                ab.file(f"test/{directory}/__init__.py")
        ab.file(
            ".github/workflows/test.yml",
            generator.render(path=".github/workflows/test.yml.mako", params=params),
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
        if editable_path:
            click.echo(
                f"Using editable Flaskteroids checkout: {editable_path}. "
                "The generated uv source requires this local path."
            )
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
        click.echo(f"Application ready. Run {generator.next_commands}.")
    click.echo(f"Next: cd {app_name!r}")


def _editable_framework_path():
    raw = distribution("flaskteroids").read_text("direct_url.json")
    if raw is None:
        return None
    try:
        direct_url = json.loads(raw)
        if not direct_url.get("dir_info", {}).get("editable", False):
            return None
        source = urlsplit(direct_url["url"])
        path = Path(url2pathname(source.path))
        if (
            source.scheme != "file"
            or source.netloc not in ("", "localhost")
            or not path.is_absolute()
        ):
            raise ValueError("editable source must be an absolute local file URL")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise click.ClickException(
            f"Cannot read editable Flaskteroids source from direct_url.json: {error}"
        ) from error
    return path
