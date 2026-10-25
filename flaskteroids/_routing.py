from dataclasses import dataclass

from flaskteroids.inflector import inflector

HTTP_METHODS = frozenset(
    {"GET", "HEAD", "PUT", "POST", "DELETE", "OPTIONS", "PATCH", "LINK", "UNLINK"}
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
