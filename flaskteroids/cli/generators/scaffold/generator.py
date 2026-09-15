import click
import yaml
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.model import generator as model
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.cli.generators.templates import template
from flaskteroids.cli.generators.scaffold import cmd_parser


def generate(name: str, args: list[str]):
    params = cmd_parser.parse(name, args)['parsed']
    ab = ArtifactsBuilder('.', click.echo)
    plural = params['plural']
    singular = params['singular']
    ab.file(
        f'app/controllers/{plural}_controller.py',
        _template(path='app/controllers/controller.py.mako', params=params)
    )
    ab.file(f'app/views/{plural}/index.html', _template(path='app/views/index.html.mako', params=params))
    ab.file(f'app/views/{plural}/new.html', _template(path='app/views/new.html.mako', params=params))
    ab.file(f'app/views/{plural}/edit.html', _template(path='app/views/edit.html.mako', params=params))
    ab.file(f'app/views/{plural}/show.html', _template(path='app/views/show.html.mako', params=params))
    ab.file(f'app/views/{plural}/_form.html', _template(path='app/views/_form.html.mako', params=params))
    ab.file(f'app/views/{plural}/_{singular}.html', _template(path='app/views/_record.html.mako', params=params))
    ab.file(
        f'test/controllers/{plural}_controller_test.py',
        _controller_test(params),
    )
    ab.file(f'test/fixtures/{plural}.yml', _fixtures(params))
    ab.file(f'test/system/{plural}_test.py', _system_test(params))
    ab.modify_py_file('config/routes.py', add_routes([
        f"route.resources('{plural}')",
    ]))
    model.generate(params['model'], args)


def _controller_test(params):
    singular = params["singular"]
    plural = params["plural"]
    model = params["model"]
    attributes = ",\n                        ".join(
        f'"{field["name"]}": self.{singular}.{field["name"]}'
        for field in params["fields"]
    )
    return f'''from test.test_helper import IntegrationTest, delete, get, patch, post
from app.models.{singular} import {model}
from flaskteroids.routes import (
    edit_{singular}_url,
    new_{singular}_url,
    {singular}_url,
    {plural}_url,
)


class {params["controller"]}ControllerTest(IntegrationTest):
    fixtures = ["{plural}"]

    def setup(self):
        self.{singular} = self.{plural}("one")

    def test_should_get_index(self):
        get({plural}_url())

        self.assert_response("success")

    def test_should_get_new(self):
        get(new_{singular}_url())

        self.assert_response("success")

    def test_should_create_{singular}(self):
        with self.assert_difference({model}.count):
            post(
                {plural}_url(),
                params={{
                    "{singular}": {{
                        {attributes}
                    }}
                }},
            )

        self.assert_redirected_to({singular}_url({model}.last()))

    def test_should_show_{singular}(self):
        get({singular}_url(self.{singular}))

        self.assert_response("success")

    def test_should_get_edit(self):
        get(edit_{singular}_url(self.{singular}))

        self.assert_response("success")

    def test_should_update_{singular}(self):
        patch(
            {singular}_url(self.{singular}),
            params={{
                "{singular}": {{
                    {attributes}
                }}
            }},
        )

        self.assert_redirected_to({singular}_url(self.{singular}))

    def test_should_destroy_{singular}(self):
        with self.assert_difference({model}.count, by=-1):
            delete({singular}_url(self.{singular}))

        self.assert_redirected_to({plural}_url())
'''


def _system_test(params):
    singular = params["singular"]
    plural = params["plural"]
    return f'''from test.test_helper import SystemTest
from flaskteroids.routes import {plural}_path


class {params["controller"]}Test(SystemTest):
    fixtures = ["{plural}"]

    def setup(self):
        self.{singular} = self.{plural}("one")

    def test_visiting_the_index(self):
        self.visit({plural}_path())

        self.assert_selector("h1", text="{plural.title()}")
'''


def _fixtures(params):
    values = {
        field["name"]: _sample_value(field["type"], field["name"])
        for field in params["fields"]
    }
    return yaml.safe_dump(
        {"one": dict(values), "two": dict(values)}, sort_keys=False
    )


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
    return template('flaskteroids.cli.generators.scaffold', path=path, params=params)
