import click
import flaskteroids.cli.generators.migrations.generator as migrations
from flaskteroids.inflector import inflector
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.fields import attachment_pattern


def generate(model, args):
    attachments = [attachment_pattern.fullmatch(arg) for arg in args]
    attachments = [match for match in attachments if match]
    migrations.generate(f'Create{inflector.pluralize(model)}', [
        arg for arg in args if not attachment_pattern.fullmatch(arg)
    ])
    ab = ArtifactsBuilder('.', click.echo)
    snake = inflector.underscore(model)
    ab.file(f'app/models/{snake}.py', _model(name=model, attachments=attachments))
    ab.file(f'test/models/{snake}_test.py', _model_test(name=model))
    if attachments:
        click.echo('Attachments require flask attachments:install, then flask db:migrate.')


def _model_test(*, name):
    return f"""
from test.test_helper import ModelTest


class {name}Test(ModelTest):
    pass
    """


def _model(*, name, attachments=()):
    if attachments:
        rules = ',\n'.join(
            f"    has_{'many' if match.group(2) == 'attachments' else 'one'}_attached('{match.group(1)}')"
            for match in attachments
        )
        return f"""
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_one_attached, has_many_attached
from flaskteroids.rules import rules


@rules(
{rules}
)
class {name}(ApplicationModel):
    pass
    """
    return f"""
from app.models.application_model import ApplicationModel


class {name}(ApplicationModel):
    pass
    """
