import json
import re
from urllib.parse import urlsplit

from markupsafe import escape

_ATTRIBUTE_NAME = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:.-]*")
_BOOLEAN_ATTRIBUTES = frozenset(
    "allowfullscreen allowpaymentrequest async autofocus autoplay checked compact "
    "controls declare default defaultchecked defaultmuted defaultselected defer "
    "disabled enabled formnovalidate hidden indeterminate inert ismap itemscope "
    "loop multiple muted nohref nomodule noresize noshade novalidate nowrap open "
    "pauseonexit playsinline readonly required reversed scoped seamless selected "
    "sortable truespeed typemustmatch".split()
)


def attributes(values):
    result = []
    for name, value in values.items():
        if not isinstance(name, str) or not _ATTRIBUTE_NAME.fullmatch(name):
            raise ValueError(f"Invalid HTML attribute name: {name!r}")
        result.append(f'{name}="{escape(str(value))}"')
    return " ".join(result)


def tag_attributes(values):
    """Serialize Rails-style tag options, including nested data and aria attributes."""
    normalized = {}
    for name, value in values.items():
        if not isinstance(name, str):
            raise ValueError(f"Invalid HTML attribute name: {name!r}")
        name = name.removesuffix("_")
        if name in {"data", "aria"} and isinstance(value, dict):
            for key, item in value.items():
                if item is not None:
                    normalized[f"{name}-{str(key).replace('_', '-')}"] = (
                        item
                        if isinstance(item, str)
                        else json.dumps(item, separators=(",", ":"))
                    )
        elif name in _BOOLEAN_ATTRIBUTES:
            if value:
                normalized[name] = name
        elif value is not None:
            normalized[name] = str(value).lower() if isinstance(value, bool) else value
    return attributes(normalized)


def validate_url(value, *, link=False):
    url = str(value)
    allowed = {"http", "https", "mailto", "tel"} if link else {"http", "https"}
    if any(ord(character) < 32 or ord(character) == 127 for character in url):
        raise ValueError("URLs must not contain control characters")
    if urlsplit(url).scheme.lower() not in allowed | {""}:
        raise ValueError("Unsupported URL scheme")
    return url
