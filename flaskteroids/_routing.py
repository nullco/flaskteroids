from dataclasses import dataclass

HTTP_METHODS = frozenset(
    {"GET", "HEAD", "PUT", "POST", "DELETE", "OPTIONS", "PATCH", "LINK", "UNLINK"}
)


@dataclass(frozen=True)
class RouteDescription:
    endpoint: str
    parameters: tuple[str, ...]
    path: str
    json_endpoint: str | None = None
