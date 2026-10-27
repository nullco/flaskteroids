from dataclasses import dataclass

from flaskteroids.inflector import inflector

HTTP_METHODS = frozenset(
    {"GET", "HEAD", "PUT", "POST", "DELETE", "OPTIONS", "PATCH", "LINK", "UNLINK"}
)


@dataclass(frozen=True)
class RoutingConventions:
    actions: tuple[str, ...]
    formats: tuple[str, ...]
    fallback_root: str | None = None


BROWSER_ROUTES = RoutingConventions(
    actions=("index", "new", "create", "show", "edit", "update", "destroy"),
    formats=("json", "turbo_stream"),
    fallback_root="flaskteroids/welcome#show",
)
API_ROUTES = RoutingConventions(
    actions=("index", "create", "show", "update", "destroy"),
    formats=("json",),
)


def collection_route_key(name):
    return f"{name}_index" if inflector.singularize(name) == name else name


@dataclass(frozen=True)
class RouteDescription:
    endpoint: str
    parameters: tuple[str, ...]
    path: str
    json_endpoint: str | None = None
    turbo_stream_endpoint: str | None = None
