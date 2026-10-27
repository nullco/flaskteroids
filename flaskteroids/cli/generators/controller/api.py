from flaskteroids.cli.generators.controller.generator import ControllerGenerator


class APIControllerGenerator(ControllerGenerator):
    test_template = "api/controller_test.py.mako"


def generate(controller, actions, skip_routes=False):
    APIControllerGenerator().generate(controller, actions, skip_routes)
