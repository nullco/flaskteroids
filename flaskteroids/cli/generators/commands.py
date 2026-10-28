import click
from flask import current_app
from flask.cli import with_appcontext

import flaskteroids.cli.generators.mailer.generator as mailer
import flaskteroids.cli.generators.migrations.generator as migrations
import flaskteroids.cli.generators.model.generator as model
import flaskteroids.cli.generators.resource.generator as resource
from flaskteroids.cli.generators.fields import fields

_FIELD_HELP = (
    "\b\nFields:\n"
    "  Use lowercase names: name:TYPE or name:TYPE! for NOT NULL.\n"
    f"  Types: {', '.join(fields)}.\n"
    "  user:references or user:belongs_to adds a required foreign key.\n"
)


@click.group()
@with_appcontext
def generate():
    """Generate application components (alias: g).

    Run from the application root. Existing files may be overwritten.
    Review generated migrations, then apply them with flask db:migrate.
    Read each subcommand's --help for usage.

    \b
    Example:
      flask generate model --help
    """


@generate.command(
    "migration",
    epilog=_FIELD_HELP + "\n\b\nExamples:\n"
    "  flask generate migration CreatePosts title:string\n"
    "  flask generate migration AddPublishedToPosts published:boolean!\n"
    "  flask generate migration RemoveTitleFromPosts title:string\n"
    "  flask generate migration DropPosts\n",
)
@click.argument("name")
@click.argument("fields", nargs=-1)
def generate_migration(name, fields):
    """Generate a database migration.

    Does not apply it. Use Create<TABLE>, Drop<TABLE>, Add<X>To<TABLE>, or
    Remove<X>From<TABLE> for NAME. Use CamelCase; CreatePosts targets posts.
    FIELDS specifies the
    columns to create, add, or remove. Drop needs no fields; Remove also
    accepts bare column names.

    Review before applying. Dropped tables and added references need manual
    rollback code; restoring removed columns requires their types. Rollback
    cannot recover deleted data.
    """
    migrations.generate(name, list(fields))


@generate.command(
    "model",
    epilog=_FIELD_HELP + "\n\b\nExample:\n"
    "  flask generate model Post title:string user:references\n",
)
@click.argument("name")
@click.argument("fields", nargs=-1)
def generate_model(name, fields):
    """Generate a model, migration, and tests.

    NAME is a singular CamelCase model name, such as Post.
    avatar:attachment and documents:attachments declare file attachments.
    Install their tables with flask attachments:install before migrating.
    content:rich_text declares rich text; run flask rich_text:install before migrating.
    """
    model.generate(name, list(fields))


@generate.command("controller")
@click.argument("name")
@click.argument("actions", nargs=-1)
@click.option(
    "--skip-routes", is_flag=True, help="Do not add routes for the generated actions."
)
def generate_controller(name, actions, skip_routes):
    """Generate a controller and request tests.

    Use a CamelCase NAME without the Controller suffix. Optional ACTIONS
    get request tests and, in browser apps, views/helpers. Adds a GET route per
    action unless --skip-routes is set.

    \b
    Examples:
      flask generate controller Posts index show
      flask generate controller Posts index --skip-routes
    """
    generators = current_app.extensions["flaskteroids.stack"].generators
    generators.controller.generate(name, actions, skip_routes)


@generate.command("mailer")
@click.argument("name")
@click.argument("actions", nargs=-1)
def generate_mailer(name, actions):
    """Generate a mailer, templates, and tests.

    Includes HTML/text templates. Use a CamelCase NAME without the Mailer
    suffix. ACTIONS are optional
    mail method names. Customize recipients, subjects, and templates before use.

    \b
    Example:
      flask generate mailer Notifications welcome
    """
    mailer.generate(name, actions)


@generate.command(
    "scaffold",
    epilog=_FIELD_HELP + "\n\b\nExample:\n"
    "  flask generate scaffold Post title:string content:text\n",
)
@click.argument("name")
@click.argument("fields", nargs=-1)
def generate_scaffold(name, fields):
    """Generate resource CRUD with tests and fixtures.

    Use a singular model NAME, such as Post. Includes the model, migration,
    controller, and routes. API apps get JSON actions and request tests; browser
    apps also get views and a browser test. Complete fixtures for any
    required references before running tests. avatar:attachment and
    documents:attachments include file inputs and permitted upload parameters.
    Install their tables with flask attachments:install before migrating.
    content:rich_text includes a Lexxy editor and safe display.
    Run flask rich_text:install before migrating.
    """
    generators = current_app.extensions["flaskteroids.stack"].generators
    generators.scaffold.generate(name, list(fields))


@generate.command(
    "resource",
    epilog=_FIELD_HELP + "\n\b\nExample:\n"
    "  flask generate resource Post title:string\n",
)
@click.argument("name")
@click.argument("fields", nargs=-1)
def generate_resource(name, fields):
    """Generate a resource skeleton with tests.

    Includes a model, migration, empty controller, and routes. Use a singular
    model NAME, such as Post. Unlike scaffold, this does not
    generate actions, views, or fixtures; implement the actions you need.
    avatar:attachment and documents:attachments declare file attachments.
    Install their tables with flask attachments:install before migrating.
    content:rich_text declares rich text; run flask rich_text:install before migrating.
    """
    resource.generate(name, list(fields))


@generate.command("authentication")
def generate_authentication():
    """Generate login, logout, and password reset.

    Includes tests. Updates application-wide authentication and routes.
    Existing User, Session, or authentication files may be overwritten. Does not include
    user registration. Review migrations and configure mail delivery before use.

    \b
    Example:
      flask generate authentication
    """
    generators = current_app.extensions["flaskteroids.stack"].generators
    generators.authentication.generate()
