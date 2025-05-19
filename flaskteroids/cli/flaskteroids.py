import os
import textwrap
import click
from pathlib import Path


@click.group()
def cli():
    pass


@cli.command('new')
@click.argument('app_name')
def new(app_name):
    NewAppBuilder(os.path.abspath(app_name)).build()


class NewAppBuilder:

    def __init__(self, base_path: str):
        self._base_path = base_path

    def build(self):
        try:
            os.makedirs(self._base_path, exist_ok=True)
            self._file('README.md')
            self._file('Dockerfile')
            self._file('.gitignore', _gitignore())
            self._file('.flaskenv', _flaskenv())
            self._file('run.py', _run())
            self._dir('db/')
            self._dir('app/')
            self._file('app/assets/stylesheets/application.css')
            self._file('app/assets/images/.keep')
            self._file('app/helpers/application_helper.py')
            self._file('app/models/application_model.py')
            self._file('app/jobs/application_job.py')
            self._file('app/mailers/application_mailer.py', _application_mailer())
            self._file('app/views/layouts/application.html')
            self._file('app/views/layouts/mailer.html')
            self._file('app/views/layouts/mailer.txt')
            self._file('app/controllers/application_controller.py', _application_controller())
            self._file('config/routes.py', _routes())
        except Exception as e:
            click.echo(f"Error creating new flaskteroids app: {e}")

    def _join(self, name):
        return Path(self._base_path, name)

    def _dir(self, name):
        os.makedirs(self._join(name), exist_ok=True)
        click.echo(f"    create  {name}")

    def _file(self, name, contents=None):
        file_path = self._join(name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch(exist_ok=True)
        if contents:
            file_path.write_text(self._clean(contents))
        click.echo(f"    create  {name}")

    def _clean(self, txt: str):
        return textwrap.dedent(txt).lstrip()


def _gitignore():
    return """
__pycache__/
db/database.db
db/jobs_database.db
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


def _run():
    return """
import logging
from flaskteroids.app import create_app

app = create_app(__name__)
jobs_app = app.extensions['flaskteroids.jobs']


if __name__ == '__main__':
    app.run(debug=True)
    """


def _flaskenv():
    return """
FLASK_APP=run.py
    """


def _migrate_sript():
    return """
\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
    """


def _migrate_env():
    return """
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    \"\"\"Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    \"\"\"
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    \"\"\"Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    \"\"\"
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            transaction_per_migration=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
    """


def _migrate_alembic():
    return """
# A generic, single database configuration.

[alembic]
# template used to generate migration files
file_template =  %%(year)d%%(month).2d%%(day).2d%%(hour).2d%%(minute).2d%%(second).2d_%%(slug)s


# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
    """
