import os
import secrets
import click
import yaml
from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException
from flaskteroids.cli.generators.templates import template
from flaskteroids.credentials import encrypt, generate_key


@click.group()
def cli():
    pass


@cli.command("new")
@click.argument("app_name")
def new(app_name):
    base_path = os.path.abspath(app_name)
    ab = ArtifactsBuilder(base_path, click.echo)
    try:
        ab.dir()
        ab.file("README.md", _readme(app_name))
        ab.file("Dockerfile", _dockerfile())
        ab.file(".dockerignore", _dockerignore())
        ab.file(".gitignore", _gitignore())
        ab.file("pyproject.toml", _pyproject_toml(app_name))
        ab.file("config/application.py", _application_config())
        ab.file("config/boot.py", _boot())
        ab.file("config/environment.py", _environment())
        ab.file("config/environments/development.py", _development_environment())
        ab.file("config/environments/test.py", _test_environment())
        ab.file("config/environments/production.py", _production_environment())
        ab.file("config/initializers/.keep")
        ab.file("config/database.yml", _database_yml())
        credentials_key = generate_key()
        credentials = yaml.safe_dump(
            {"secret_key_base": secrets.token_hex(64)}, sort_keys=False
        )
        ab.file("config/master.key", f"{credentials_key}\n")
        ab.file("config/credentials.yml.enc", encrypt(credentials, credentials_key))
        ab.file("wsgi.py", _wsgi())
        ab.file("jobs.py", _jobs())
        # Kamal deploy scaffold (example files) — adjust image/commands for your setup
        ab.file("kamal.yml", _kamal_yml())
        ab.file(".github/workflows/deploy.yml", _deploy_workflow())
        ab.file("deploy/release.sh", _deploy_release())
        # Rails-like default helpers
        ab.file("bin/release", _bin_release())
        ab.file("bin/setup", _bin_setup())
        ab.file("Procfile", _procfile())
        ab.file("deploy/README.md", _deploy_readme())
        ab.file("storage/.keep")
        ab.dir("db/")
        ab.dir("app/")
        ab.file("app/assets/stylesheets/application.css")
        ab.file("app/assets/images/.keep")
        ab.file("app/helpers/application_helper.py", _application_helper())
        ab.file("app/models/application_model.py", _application_model())
        ab.file("app/jobs/application_job.py")
        ab.file("app/mailers/application_mailer.py", _application_mailer())
        ab.file(
            "app/views/layouts/application.html",
            _template(path="app/views/layouts/application.html.mako"),
        )
        ab.file("app/views/layouts/mailer.html")
        ab.file("app/views/layouts/mailer.txt")
        ab.file("app/controllers/application_controller.py", _application_controller())
        ab.file("config/routes.py", _routes())
        ab.python_run("flask db:init")
        ab.file("db/migrate/versions/.keep")
        ab.run("git init")
        ab.run("git branch -m main")
    except ArtifactsBuilderException as e:
        click.echo(f"Error creating new flaskteroids app: {e}")


def _gitignore():
    return """
__pycache__/
.venv/
storage/*
!storage/.keep
config/master.key
config/credentials/*.key
    """


def _dockerignore():
    return """
.git/
.venv/
__pycache__/
config/master.key
config/credentials/*.key
    """


def _readme(app_name):
    return f"""
# {app_name.replace("_", " ").title()}

Add your project description here
    """


def _pyproject_toml(app_name):
    return f"""
[project]
name = "{app_name}"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
    requires-python = ">=3.12"
dependencies = [
    "flaskteroids",
]
    """


def _application_helper():
    return """
class ApplicationHelper:
    pass
    """


def _application_model():
    return """
from flaskteroids.model import Model


class ApplicationModel(Model):
    pass
    """


def _application_controller():
    return """
from flaskteroids.controller import ActionController


class ApplicationController(ActionController):
    pass
    """


def _application_mailer():
    return """
from flaskteroids.mailer import ActionMailer


class ApplicationMailer(ActionMailer):
    pass
    """


def _routes():
    return """
def register(route):
    route.get('/up/', to="flaskteroids/health#show")
    """


def _application_config():
    return """
from flaskteroids.application import Application as FlaskteroidsApplication
from config.boot import ROOT


class Application(FlaskteroidsApplication):
    root = ROOT

    def configure(self, config):
        config.load_defaults('0.1')
    """


def _boot():
    return """
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
    """


def _environment():
    return """
from config.application import Application

application = Application.initialize()
    """


def _development_environment():
    return """
def configure(config):
    config.enable_reloading = True
    config.consider_all_requests_local = True
    config.action_controller.perform_caching = False
    config.action_mailer.perform_deliveries = False
    """


def _test_environment():
    return """
def configure(config):
    config.enable_reloading = False
    config.eager_load = False
    config.action_controller.perform_caching = False
    config.action_mailer.perform_deliveries = False
    """


def _production_environment():
    return """
import os


def configure(config):
    config.eager_load = True
    config.consider_all_requests_local = False
    config.require_master_key = True
    config.action_mailer.perform_deliveries = True
    config.active_job.broker_url = os.environ.get(
        'CELERY_BROKER_URL', config.active_job.broker_url
    )
    """


def _database_yml():
    return """
default: &default
  adapter: sqlite3
  pool: 5

development:
  <<: *default
  database: storage/development.sqlite3

test:
  <<: *default
  database: storage/test.sqlite3

production:
  <<: *default
  database: storage/production.sqlite3
    """


def _wsgi():
    return """
from config.environment import application as app

if __name__ == '__main__':
    app.run(debug=app.env.development)
    """


def _jobs():
    return """
from config.environment import application

app = application.extensions['flaskteroids.jobs']
    """


def _template(*, path, params=None):
    return template("flaskteroids.cli", path=path, params=params)


def _dockerfile():
    # Use a raw string to avoid accidental escape-sequence warnings (eg. file:\/\/) in Dockerfile contents
    return r"""
# Simplified multi-stage Dockerfile using uv's official image to produce a
# pinned requirements.txt, then installing dependencies in a minimal Python image.

# Use a standard Python image for build stage (provides /bin/sh),
# but copy uv binaries from the official uv image so we use the same uv
FROM python:3.12-slim AS deps
WORKDIR /app

# Copy uv binaries from the official uv image into this build stage
# The official uv image exposes `uv` and `uvx` at the image root
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:0.10.7 /uvx /usr/local/bin/uvx
RUN chmod +x /usr/local/bin/uv /usr/local/bin/uvx
ENV PATH="/usr/local/bin:${PATH}"

# Copy project files and sync dependencies with uv.
# uv will create a .venv; we then freeze its installed packages to requirements.txt
    COPY . .
    # Run uv sync (no --production flag; use default behavior)
    RUN uv sync \
    && .venv/bin/pip freeze | sed '/^-e /d; /file:\/\//d' > /requirements.txt

FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Minimal runtime deps (add others as needed, e.g. libpq5 for PostgreSQL drivers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pinned requirements generated by the deps stage and install them
COPY --from=deps /requirements.txt /requirements.txt
# Ensure pip installs runtime dependency 'flaskteroids' in case it was
# omitted from the pinned requirements (ensures scaffolded apps run)
RUN pip install --no-cache-dir -r /requirements.txt gunicorn flaskteroids

# Copy application source
COPY . .

# Run as unprivileged user
RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "wsgi:app", "-b", "0.0.0.0:8000", "--workers", "4"]
    """


def _kamal_yml():
    return """
# Example kamal configuration for a Flaskteroids app.
# Update image names, environment and secrets as needed.
services:
  web:
    # Use the IMAGE env var set by your CI; fallback shows a placeholder
    image: ${IMAGE:-REPLACE_WITH_IMAGE}
    command: gunicorn wsgi:app -b 0.0.0.0:8000 --workers 4
    ports:
      - 80:8000
    env:
      FLASKTEROIDS_ENV: production
      DATABASE_URL: ${{ DATABASE_URL }}
      FLASKTEROIDS_MASTER_KEY: ${{ FLASKTEROIDS_MASTER_KEY }}
    mounts:
      - type: tmpfs
        target: /tmp

  worker:
    image: ${IMAGE:-REPLACE_WITH_IMAGE}
    command: celery -A jobs worker --loglevel=info
    env:
      FLASKTEROIDS_ENV: production
      DATABASE_URL: ${{ DATABASE_URL }}
      CELERY_BROKER_URL: ${{ CELERY_BROKER_URL }}
      FLASKTEROIDS_MASTER_KEY: ${{ FLASKTEROIDS_MASTER_KEY }}

  hooks:
  release:
    - name: migrate
      # Call the Rails/Heroku-style release script if present
      command: bash /srv/myapp/bin/release migrate
      only_on: leader
"""


def _deploy_workflow():
    return """
name: Build and deploy

on:
  push:
    branches: [ main ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    env:
      IMAGE: ghcr.io/${{ github.repository }}:${{ github.sha }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v2
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push image
        uses: docker/build-push-action@v4
        with:
          push: true
          tags: ${{ env.IMAGE }}

      - name: Deploy with Kamal over SSH
        env:
          IMAGE: ${{ env.IMAGE }}
        run: |
          mkdir -p ~/.ssh
          echo "$DEPLOY_SSH_KEY" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh -o StrictHostKeyChecking=no -i ~/.ssh/id_rsa ${{ secrets.DEPLOY_USER }}@${{ secrets.DEPLOY_HOST }} \
            "cd /srv/myapp && kamal deploy --image $IMAGE"
        shell: bash
        # Requires repository secrets: DEPLOY_SSH_KEY, DEPLOY_HOST, DEPLOY_USER,
        # FLASKTEROIDS_MASTER_KEY, and application service secrets.
"""


def _deploy_release():
    return """
#!/usr/bin/env bash
set -euo pipefail

cmd=${1:-}
case "$cmd" in
  migrate)
    echo "Running migrations..."
    # Activate venv if you use one, or run via python -m
    python -m flask db:migrate
    ;;
  *)
    echo "Unknown release command: $cmd"
    exit 1
    ;;
esac
"""


def _deploy_readme():
    return """
Kamal deployment files

Place your built Docker image reference in `kamal.yml` under each service's `image`.
The release hook calls `deploy/release.sh migrate` on the leader host to run DB migrations.

Adjust the `command` fields and environment variables to match your app and hosting setup.
"""


def _bin_release():
    return """
#!/usr/bin/env bash
# Default release helper similar to Rails/Heroku
set -euo pipefail
echo "Running release tasks..."
case "${1:-}" in
  migrate)
    python -m flask db:migrate
    ;;
  assets:precompile)
    # If you precompile assets during build, skip. Placeholder for app teams.
    echo "Assets precompile not configured"
    ;;
  *)
    echo "Usage: $0 {migrate|assets:precompile}"
    exit 1
    ;;
esac
"""


def _bin_setup():
    return """
#!/usr/bin/env bash
# Setup script to initialize local dev environment. Runs once per new app.
set -euo pipefail
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || true
python -m flask db:init || true
echo "Setup complete"
"""


def _procfile():
    return """
web: gunicorn wsgi:app -b 0.0.0.0:$PORT --workers 4
worker: celery -A jobs worker --loglevel=info
"""
