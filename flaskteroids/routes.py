from flask import current_app, url_for


class RouteHelper:
    def __init__(self, name):
        self.name = name
        self.external = name.endswith("_url")
        self.route_name = name.removesuffix("_url").removesuffix("_path")

    def __call__(self, record=None, **values):
        routes = current_app.extensions["flaskteroids.routes"]
        helper = routes.helpers.get(self.route_name)
        if helper is None:
            raise AttributeError(f"Unknown route helper <{self.name}>")
        if record is not None:
            parameter = helper.get("param")
            if parameter:
                values.setdefault(parameter, getattr(record, "id", record))
        return url_for(helper["endpoint"], _external=self.external, **values)


def __getattr__(name):
    if name.endswith(("_path", "_url")):
        return RouteHelper(name)
    raise AttributeError(name)
