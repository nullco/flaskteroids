from base64 import b64encode
from importlib.resources import files

from flask import render_template_string

from flaskteroids import __version__ as version
from flaskteroids.controller import ActionController


class WelcomeController(ActionController):
    def show(self):
        templates = files("flaskteroids").joinpath("controllers/templates")
        images = {
            name: "data:image/svg+xml;base64,"
            + b64encode(templates.joinpath(f"brand/{name}.svg").read_bytes()).decode(
                "ascii"
            )
            for name in ("logo-horizontal-light", "logo-horizontal-dark", "favicon")
        }
        return render_template_string(
            templates.joinpath("welcome.html").read_text(encoding="utf-8"),
            images=images,
            version=version,
        )
