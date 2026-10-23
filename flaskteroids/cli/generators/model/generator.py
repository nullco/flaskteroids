import click

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.fields import (
    association_pattern,
    attachment_pattern,
    rich_text_pattern,
)
from flaskteroids.cli.generators.migrations import generator as migrations
from flaskteroids.cli.generators.templates import template
from flaskteroids.inflector import inflector


def generate(model, args):
    attachments = []
    rich_texts = []
    fields = []
    for arg in args:
        if match := rich_text_pattern.fullmatch(arg):
            rich_texts.append(match.group(1))
            continue
        match = attachment_pattern.fullmatch(arg)
        if match:
            attachments.append(
                {
                    "name": match.group(1),
                    "cardinality": "many" if match.group(2) == "attachments" else "one",
                }
            )
        else:
            fields.append(arg)
    migrations.generate(f"Create{inflector.pluralize(model)}", fields)
    ab = ArtifactsBuilder(".", click.echo)
    snake = inflector.underscore(model)
    params = {
        "name": model,
        "attachments": attachments,
        "rich_texts": rich_texts,
        "references": [
            match[1]
            for field in fields
            if (match := association_pattern.fullmatch(field))
        ],
    }
    ab.file(
        f"app/models/{snake}.py",
        template(
            "flaskteroids.cli.generators.model", path="model.py.mako", params=params
        ),
    )
    ab.file(
        f"test/models/{snake}_test.py",
        template(
            "flaskteroids.cli.generators.model",
            path="model_test.py.mako",
            params=params,
        ),
    )
    if rich_texts:
        click.echo("Rich text requires flask rich_text:install, then flask db:migrate.")
    if attachments:
        click.echo(
            "Attachments require flask attachments:install, then flask db:migrate."
        )
