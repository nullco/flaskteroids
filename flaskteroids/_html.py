import re
from urllib.parse import urlsplit

from markupsafe import escape

_ATTRIBUTE_NAME = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:.-]*")


def attributes(values):
    result = []
    for name, value in values.items():
        if not isinstance(name, str) or not _ATTRIBUTE_NAME.fullmatch(name):
            raise ValueError(f"Invalid HTML attribute name: {name!r}")
        result.append(f'{name}="{escape(str(value))}"')
    return " ".join(result)


def validate_url(value, *, link=False):
    url = str(value)
    allowed = {"http", "https", "mailto", "tel"} if link else {"http", "https"}
    if any(ord(character) < 32 or ord(character) == 127 for character in url):
        raise ValueError("URLs must not contain control characters")
    if urlsplit(url).scheme.lower() not in allowed | {""}:
        raise ValueError("Unsupported URL scheme")
    return url
