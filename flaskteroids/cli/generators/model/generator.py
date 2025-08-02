import click
import flaskteroids.cli.generators.migrations.generator as migrations
from flaskteroids.inflector import inflector
from flaskteroids.cli.artifacts import ArtifactsBuilder


def generate(model, args):
    migrations.generate(f'Create{inflector.pluralize(model)}', args)
    ab = ArtifactsBuilder('.', click.echo)
    ab.file(f'app/models/{inflector.underscore(model)}.py', _model(name=model))


def _model(*, name):
    return f"""
from app.models.application_model import ApplicationModel


class {name}(ApplicationModel):
    pass
    """
