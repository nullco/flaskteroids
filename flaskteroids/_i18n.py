"""Catalog storage and locale-independent date formatting."""

import re
from copy import deepcopy
from datetime import date, datetime, time
from pathlib import Path
from threading import RLock

import yaml


class TranslationError(ValueError):
    """A catalog entry or translation argument is invalid."""


class InvalidLocale(TranslationError):
    pass


class MissingTranslation(TranslationError):
    pass


class MissingInterpolationArgument(TranslationError):
    pass


_ENGLISH = {
    "date": {
        "formats": {
            "default": "%Y-%m-%d",
            "short": "%b %d",
            "long": "%B %d, %Y",
        },
        "day_names": [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ],
        "abbr_day_names": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "month_names": [
            None,
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        "abbr_month_names": [
            None,
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ],
    },
    "time": {
        "formats": {
            "default": "%a, %d %b %Y %H:%M:%S %z",
            "short": "%d %b %H:%M",
            "long": "%B %d, %Y %H:%M",
        },
        "am": "am",
        "pm": "pm",
    },
}
_MISSING = object()


def _merge(target, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _validate(data, path, depth=0):
    if depth > 40:
        raise TranslationError(f"Catalog nesting is too deep: {path}")
    if isinstance(data, dict):
        for key, value in data.items():
            if not isinstance(key, str) or not key or "." in key:
                raise TranslationError(f"Catalog keys must be nonempty strings: {path}")
            _validate(value, path, depth + 1)
    elif isinstance(data, list):
        if any(value is not None and not isinstance(value, str) for value in data):
            raise TranslationError(
                f"Catalog lists must contain strings or null: {path}"
            )
    elif data is not None and not isinstance(data, str):
        raise TranslationError(f"Catalog values must be strings: {path}")


class Catalog:
    def __init__(self, path):
        self.path = Path(path)
        self._data = None
        self._lock = RLock()

    def reload(self):
        # Build before publishing, so readers never see a partly loaded catalog.
        with self._lock:
            data = {"en": deepcopy(_ENGLISH)}
            paths = sorted({*self.path.rglob("*.yml"), *self.path.rglob("*.yaml")})
            for path in paths:
                try:
                    content = yaml.safe_load(path.read_text(encoding="utf-8"))
                except (yaml.YAMLError, UnicodeError) as error:
                    raise TranslationError(
                        f"Invalid translation catalog: {path}"
                    ) from error
                if not isinstance(content, dict):
                    raise TranslationError(
                        f"Catalog must contain a locale mapping: {path}"
                    )
                _validate(content, path)
                for locale, entries in content.items():
                    if not isinstance(entries, dict):
                        raise TranslationError(f"Locale must contain a mapping: {path}")
                    _merge(data.setdefault(locale, {}), entries)
            self._data = data

    def lookup(self, locale, key):
        with self._lock:
            if self._data is None:
                self.reload()
            value = self._data.get(locale, {})
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return _MISSING
            value = value[part]
        return _MISSING if value is None else value


def format_datetime(value, pattern, lookup):
    """Use catalog names, never the process-global C locale."""
    if not isinstance(value, (date, datetime, time)):
        raise TypeError("localize() expects a date, datetime, or time")
    if not isinstance(pattern, str):
        raise TranslationError("A date/time format must be a string")

    def names(key, index, size):
        entries = lookup(f"date.{key}")
        if (
            not isinstance(entries, list)
            or len(entries) != size
            or not isinstance(entries[index], str)
        ):
            raise TranslationError(f"Invalid date.{key} translation")
        return entries[index]

    def directive(match):
        unpadded, code = match.groups()
        if code == "%":
            return "%"
        if code in "aAbBh":
            if isinstance(value, time):
                raise TranslationError(f"%{code} requires a date")
            if code in "aA":
                key = "day_names" if code == "A" else "abbr_day_names"
                return names(key, (value.weekday() + 1) % 7, 7)
            key = "month_names" if code == "B" else "abbr_month_names"
            return names(key, value.month, 13)
        if code in "pP":
            if not isinstance(value, (datetime, time)):
                raise TranslationError(f"%{code} requires a time")
            result = lookup("time.am" if value.hour < 12 else "time.pm")
            if not isinstance(result, str):
                raise TranslationError("Invalid time.am/time.pm translation")
            return result.upper() if code == "p" else result.lower()
        if code not in "YymdejHIMSfzZwu":
            raise TranslationError(f"Unsupported date/time directive: %{code}")
        result = value.strftime("%d" if code == "e" else f"%{code}")
        if code == "e":
            return result.lstrip("0").rjust(2)
        if unpadded:
            return result.lstrip("0") or "0"
        return result

    # Splitting protects literal percent signs from being interpreted twice.
    pieces = re.split(r"(%-?.|%$)", pattern, flags=re.DOTALL)
    result = []
    for piece in pieces:
        if piece.startswith("%"):
            match = re.fullmatch(r"%(-?)(.)", piece)
            if match is None:
                raise TranslationError("Incomplete date/time directive")
            result.append(directive(match))
        else:
            result.append(piece)
    return "".join(result)
