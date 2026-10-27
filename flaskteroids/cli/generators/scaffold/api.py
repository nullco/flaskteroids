from flaskteroids.cli.generators.scaffold.generator import (
    ScaffoldGenerator,
    _sample_value,
)


class APIScaffoldGenerator(ScaffoldGenerator):
    controller_template = "api/controller.py.mako"
    test_template = "api/controller_test.py.mako"

    def _field_values(self, params):
        values = [
            f"{field['name']!r}: {_sample_value(field['type'], field['name'])!r}"
            for field in params["fields"]
        ]
        values.extend(
            f'"{field["name"]}": self.{params["singular"]}.{field["name"]}'
            for field in params["references"]
        )
        return values


def generate(name, args):
    APIScaffoldGenerator().generate(name, args)
