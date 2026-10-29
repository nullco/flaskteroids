"""Application artifact strategies; templates never choose an application mode."""

from typing import ClassVar

from flaskteroids.cli.generators.templates import template
from flaskteroids.importmaps.installation import application_files


class ApplicationGenerator:
    template_overrides: ClassVar[dict[str, str]] = {}
    test_directories = ("fixtures", "models", "controllers", "mailers", "jobs")
    next_commands = ("bin/flask run", "bin/flask test")

    def __init__(self, params):
        self.params = params

    def render(self, *, path, params=None):
        return template(
            "flaskteroids.cli",
            path=self.template_overrides.get(path, path),
            params=self.params | (params or {}),
        )

    def write_presentation(self, ab):
        pass


class BrowserApplicationGenerator(ApplicationGenerator):
    test_directories = (*ApplicationGenerator.test_directories, "system")
    next_commands = (*ApplicationGenerator.next_commands, "bin/flask test:system")

    def write_presentation(self, ab):
        ab.file("app/assets/stylesheets/application.css")
        ab.file("app/assets/images/.keep")
        ab.file("vendor/javascript/.keep")
        for destination, content in application_files().items():
            ab.file(destination, content)
        for destination in (
            "app/helpers/application_helper.py",
            "app/views/layouts/application.html",
        ):
            ab.file(destination, self.render(path=destination + ".mako"))


class APIApplicationGenerator(ApplicationGenerator):
    template_overrides: ClassVar[dict[str, str]] = {
        path: "api/" + path
        for path in (
            "README.md.mako",
            "Dockerfile.mako",
            ".github/workflows/test.yml.mako",
            "config/application.py.mako",
            "app/controllers/application_controller.py.mako",
            "deploy/README.md.mako",
            "test/test_helper.py.mako",
        )
    }


def application_generator(api_only, params):
    generator = APIApplicationGenerator if api_only else BrowserApplicationGenerator
    return generator(params)
