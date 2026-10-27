from importlib.resources import files

from flask import render_template_string

from flaskteroids import __version__ as version
from flaskteroids._branding import brand_images
from flaskteroids.controller import Controller


class WelcomeController(Controller):
    def show(self):
        templates = files("flaskteroids").joinpath("controllers/templates")
        images = brand_images(
            "logo-horizontal-light", "logo-horizontal-dark", "favicon"
        )
        return render_template_string(
            templates.joinpath("welcome.html").read_text(encoding="utf-8"),
            images=images,
            version=version,
        )
