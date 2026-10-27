import click

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.mailer import cmd_parser
from flaskteroids.cli.generators.templates import template


def generate(mailer, actions):
    parsed = cmd_parser.parse(mailer, [])["parsed"]
    snake = parsed["snake"]
    params = {"name": parsed["camel"], "snake": snake, "actions": actions}
    ab = ArtifactsBuilder(".", click.echo)
    ab.file(f"app/mailers/{snake}_mailer.py", _template("mailer.py.mako", params))
    ab.dir(f"app/views/{snake}_mailer/")
    ab.file(
        f"test/mailers/previews/{snake}_mailer_preview.py",
        _template("preview.py.mako", params),
    )
    ab.file(
        f"test/mailers/{snake}_mailer_test.py", _template("mailer_test.py.mako", params)
    )
    for action in actions:
        html_file_name = f"app/views/{snake}_mailer/{action}.html"
        txt_file_name = f"app/views/{snake}_mailer/{action}.txt"
        ab.file(
            html_file_name,
            _template(
                "view.html.mako",
                {**params, "action": action, "file_name": html_file_name},
            ),
        )
        ab.file(
            txt_file_name,
            _template(
                "view.txt.mako",
                {**params, "action": action, "file_name": txt_file_name},
            ),
        )


def _template(path, params):
    return template("flaskteroids.cli.generators.mailer", path=path, params=params)
