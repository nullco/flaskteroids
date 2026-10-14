import click
import yaml

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.model import generator as model
from flaskteroids.cli.generators.scaffold import cmd_parser
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.cli.generators.templates import template


def generate(name: str, args: list[str]):
    params = cmd_parser.parse(name, args)["parsed"]
    ab = ArtifactsBuilder(".", click.echo)
    plural = params["plural"]
    singular = params["singular"]
    ab.file(
        f"app/controllers/{plural}_controller.py",
        _template(path="app/controllers/controller.py.mako", params=params),
    )
    ab.file(
        f"app/views/{plural}/index.html",
        _template(path="app/views/index.html.mako", params=params),
    )
    ab.file(
        f"app/views/{plural}/new.html",
        _template(path="app/views/new.html.mako", params=params),
    )
    ab.file(
        f"app/views/{plural}/edit.html",
        _template(path="app/views/edit.html.mako", params=params),
    )
    ab.file(
        f"app/views/{plural}/show.html",
        _template(path="app/views/show.html.mako", params=params),
    )
    ab.file(
        f"app/views/{plural}/_form.html",
        _template(path="app/views/_form.html.mako", params=params),
    )
    ab.file(
        f"app/views/{plural}/_{singular}.html",
        _template(path="app/views/_record.html.mako", params=params),
    )
    ab.file(
        f"test/controllers/{plural}_controller_test.py",
        _controller_test(params),
    )
    ab.file(f"test/fixtures/{plural}.yml", _fixtures(params))
    if params["attachments"]:
        ab.file("test/fixtures/files/attachment.txt", "An example attachment.\n")
    ab.file(f"test/system/{plural}_test.py", _system_test(params))
    ab.modify_py_file(
        "config/routes.py",
        add_routes(
            [
                f"route.resources('{plural}')",
            ]
        ),
    )
    model.generate(params["model"], args)


def _controller_test(params):
    singular = params["singular"]
    plural = params["plural"]
    model = params["model"]
    values = [
        f'"{field["name"]}": self.{singular}.{field["name"]}'
        for field in params["fields"]
    ]
    for attachment in params["attachments"]:
        upload = 'fixture_file_upload("attachment.txt")'
        if attachment["type"] == "attachments":
            upload = f"[{upload}]"
        values.append(f'"{attachment["name"]}": {upload}')
    attributes = ",\n                        ".join(values)
    upload_import = (
        "\nfrom flaskteroids.testing import fixture_file_upload"
        if params["attachments"]
        else ""
    )
    return _template(
        path="test/controllers/controller_test.py.mako",
        params={
            **params,
            "singular": singular,
            "plural": plural,
            "model": model,
            "attributes": attributes,
            "upload_import": upload_import,
        },
    )


def _system_test(params):
    singular = params["singular"]
    plural = params["plural"]
    return _template(
        path="test/system/system_test.py.mako",
        params={**params, "singular": singular, "plural": plural},
    )


def _fixtures(params):
    values = {
        field["name"]: _sample_value(field["type"], field["name"])
        for field in params["fields"]
    }
    return yaml.safe_dump({"one": dict(values), "two": dict(values)}, sort_keys=False)


def _sample_value(type_, name):
    if type_ in {"integer", "int"}:
        return 1
    if type_ == "float":
        return 1.5
    if type_ in {"boolean", "bool"}:
        return True
    if type_ == "datetime":
        return "2025-01-01T12:00:00"
    if type_ == "date":
        return "2025-01-01"
    if type_ == "time":
        return "12:00:00"
    if type_ == "json":
        return {}
    return f"My {name.replace('_', ' ')}"


def _template(*, path, params=None):
    return template("flaskteroids.cli.generators.scaffold", path=path, params=params)
