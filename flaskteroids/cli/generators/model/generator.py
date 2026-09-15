import click
import flaskteroids.cli.generators.migrations.generator as migrations
from flaskteroids.inflector import inflector
from flaskteroids.cli.artifacts import ArtifactsBuilder


def generate(model, args):
    migrations.generate(f'Create{inflector.pluralize(model)}', args)
    ab = ArtifactsBuilder('.', click.echo)
    snake = inflector.underscore(model)
    ab.file(f'app/models/{snake}.py', _model(name=model))
    ab.file(f'test/models/{snake}_test.py', _model_test(name=model))


def _model_test(*, name):
    return f"""
from test.test_helper import ModelTest


class {name}Test(ModelTest):
    pass
    """


def _model(*, name):
    return f"""
from app.models.application_model import ApplicationModel


class {name}(ApplicationModel):
    pass
    """
