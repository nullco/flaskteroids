import click

from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.src_modifier import add_routes
from flaskteroids.cli.generators.templates import template
from flaskteroids.inflector import inflector


class ControllerGenerator:
    test_template = "controller_test.py.mako"

    def generate(self, controller, actions, skip_routes=False):
        ab = ArtifactsBuilder(".", click.echo)
        cname = inflector.underscore(controller)
        params = {"name": controller, "path": cname, "actions": actions}
        ab.file(
            f"app/controllers/{cname}_controller.py",
            _template("controller.py.mako", params),
        )
        ab.file(
            f"test/controllers/{cname}_controller_test.py",
            _template(self.test_template, params),
        )
        self._write_presentation(ab, params)
        if not skip_routes:
            for action in actions:
                route = f"route.get('/{cname}/{action}', to='{cname}#{action}')"
                ab.modify_py_file("config/routes.py", add_routes([route]))

    def _write_presentation(self, ab, params):
        pass


class BrowserControllerGenerator(ControllerGenerator):
    def _write_presentation(self, ab, params):
        cname = params["path"]
        ab.file(f"app/helpers/{cname}_helper.py", _template("helper.py.mako", params))
        ab.dir(f"app/views/{cname}/")
        for action in params["actions"]:
            file_name = f"app/views/{cname}/{action}.html"
            ab.file(
                file_name,
                _template(
                    "view.html.mako",
                    {**params, "action": action, "file_name": file_name},
                ),
            )


def generate(controller, actions, skip_routes=False):
    BrowserControllerGenerator().generate(controller, actions, skip_routes)


def _template(path, params):
    return template("flaskteroids.cli.generators.controller", path=path, params=params)
