from uuid import UUID

from flask import current_app, url_for

from flaskteroids._routing import collection_route_key
from flaskteroids.inflector import inflector


def _parameter(value):
    from flaskteroids.model import Model

    if isinstance(value, Model):
        value = value.to_param()
    if value is None or value == "":
        raise ValueError("A persisted record or nonempty identifier is required.")
    if isinstance(value, bool) or not isinstance(value, (str, int, float, UUID)):
        raise TypeError("Route bindings must be model records or explicit identifiers.")
    return value


class RouteHelper:
    def __init__(self, name):
        self.name = name
        self.external = name.endswith("_url")
        self.route_name = name.removesuffix("_url" if self.external else "_path")

    def __call__(self, *records, **values):
        routes = current_app.extensions["flaskteroids.routes"]
        helper = routes.helpers.get(self.route_name)
        if helper is None:
            raise AttributeError(f"Unknown route helper <{self.name}>")
        if len(records) > len(helper.parameters):
            raise TypeError(
                f"<{self.name}> takes {len(helper.parameters)} route bindings."
            )
        for parameter, record in zip(helper.parameters, records, strict=False):
            if parameter in values:
                raise TypeError(f"Duplicate binding <{parameter}> for <{self.name}>.")
            values[parameter] = record
        missing = set(helper.parameters) - values.keys()
        if missing:
            raise ValueError(
                f"Missing bindings for <{self.name}>: {', '.join(sorted(missing))}"
            )
        for parameter in helper.parameters:
            values[parameter] = _parameter(values[parameter])
        format_ = values.pop("format", None)
        endpoint = helper.endpoint
        if format_ is not None:
            if format_ != "json" or helper.json_endpoint is None:
                raise ValueError(f"Unsupported format <{format_}> for <{self.name}>.")
            endpoint = helper.json_endpoint
        return url_for(endpoint, _external=self.external, **values)


def _model_destination(destination):
    from flaskteroids.model import Model

    records = (
        tuple(destination) if isinstance(destination, (list, tuple)) else (destination,)
    )
    if not records:
        raise ValueError("A model destination cannot be empty.")
    if not all(isinstance(record, Model) for record in records):
        raise TypeError("Model destinations require a record or a sequence of records.")
    return records


def _polymorphic_path(destination):
    records = _model_destination(destination)
    ancestors, target = records[:-1], records[-1]
    names = [inflector.underscore(type(record).__name__) for record in ancestors]
    target_name = inflector.underscore(type(target).__name__)
    names.append(
        target_name
        if target.is_persisted()
        else collection_route_key(inflector.pluralize(target_name))
    )
    bindings = records if target.is_persisted() else ancestors
    return RouteHelper("_".join(names) + "_path")(*bindings)


def __getattr__(name):
    if name.endswith(("_path", "_url")):
        return RouteHelper(name)
    raise AttributeError(name)
