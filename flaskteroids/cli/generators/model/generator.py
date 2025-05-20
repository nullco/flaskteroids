import click
import flaskteroids.cli.generators.migrations.generator as migrations
from flaskteroids.str_utils import camel_to_snake, pluralize
from flaskteroids.cli.artifacts import ArtifactsBuilder


def generate(model, args):
    migrations.generate(f'Create{pluralize(model).title()}Table', args)
    ab = ArtifactsBuilder('.', click.echo)
    ab.file(f'app/models/{camel_to_snake(model)}.py', _model(name=model))


def _model(*, name):
    return f"""
from app.models.application_model import ApplicationModel


class {name}(ApplicationModel):
    pass
    """
