import click
import yaml

from flaskteroids._routing import collection_route_key
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.model import generator as model
from flaskteroids.cli.generators.scaffold import cmd_parser
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.cli.generators.templates import template


class ScaffoldGenerator:
    controller_template = "app/controllers/controller.py.mako"
    test_template = "test/controllers/controller_test.py.mako"

    def generate(self, name, args):
        params = cmd_parser.parse(name, args)["parsed"]
        params["collection"] = collection_route_key(params["plural"])
        ab = ArtifactsBuilder(".", click.echo)
        plural = params["plural"]
        ab.file(
            f"app/controllers/{plural}_controller.py",
            _template(path=self.controller_template, params=params),
        )
        ab.file(
            f"test/controllers/{plural}_controller_test.py",
            self._controller_test(params),
        )
        ab.file(f"test/fixtures/{plural}.yml", _fixtures(params))
        if params["attachments"]:
            ab.file("test/fixtures/files/attachment.txt", "An example attachment.\n")
        self._write_presentation(ab, params)
        ab.modify_py_file(
            "config/routes.py", add_routes([f"route.resources('{plural}')"])
        )
        model.generate(params["model"], args)

    def _field_values(self, params):
        singular = params["singular"]
        return [
            f'"{field["name"]}": self.{singular}.{field["name"]}'
            for field in params["fields"]
        ]

    def _controller_test(self, params):
        singular = params["singular"]
        values = self._field_values(params)
        values.extend(
            f'"{name}": self.{singular}.{name}.to_editor_html()'
            for name in params["rich_texts"]
        )
        for attachment in params["attachments"]:
            upload = 'fixture_file_upload("attachment.txt")'
            if attachment["type"] == "attachments":
                upload = f"[{upload}]"
            values.append(f'"{attachment["name"]}": {upload}')
        return _template(
            path=self.test_template,
            params={
                **params,
                "attributes": ",\n                        ".join(values),
                "upload_import": (
                    "\nfrom flaskteroids.testing import fixture_file_upload"
                    if params["attachments"]
                    else ""
                ),
            },
        )

    def _write_presentation(self, ab, params):
        pass


class BrowserScaffoldGenerator(ScaffoldGenerator):
    def _write_presentation(self, ab, params):
        plural, singular = params["plural"], params["singular"]
        for view in ("index", "new", "edit", "show", "_form", "_record"):
            destination = f"_{singular}" if view == "_record" else view
            ab.file(
                f"app/views/{plural}/{destination}.html",
                _template(path=f"app/views/{view}.html.mako", params=params),
            )
        ab.file(
            f"test/system/{plural}_test.py",
            _template(path="test/system/system_test.py.mako", params=params),
        )


def generate(name: str, args: list[str]):
    BrowserScaffoldGenerator().generate(name, args)


def _fixtures(params):
    values = {
        field["name"]: _sample_value(field["type"], field["name"])
        for field in params["fields"]
    }
    values.update({name: f"<div>My {name}</div>" for name in params["rich_texts"]})
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
