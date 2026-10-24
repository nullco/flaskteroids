"""Application-local translations and scoped locale selection."""

import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

from flask import current_app, g, has_request_context, request
from jinja2 import pass_context
from markupsafe import Markup, escape

from flaskteroids._i18n import (
    _MISSING,
    Catalog,
    format_datetime,
)
from flaskteroids._i18n import InvalidLocale as InvalidLocale
from flaskteroids._i18n import (
    MissingInterpolationArgument as MissingInterpolationArgument,
)
from flaskteroids._i18n import MissingTranslation as MissingTranslation
from flaskteroids._i18n import TranslationError as TranslationError

_locale = ContextVar("flaskteroids.locale", default=None)
_INTERPOLATION = re.compile(r"%\{([^{}]+)\}")


def _scope():
    return (
        g._get_current_object(),
        request._get_current_object() if has_request_context() else None,
    )


def get_locale():
    """Return this request/execution's locale, or the application default."""
    state = _locale.get()
    if state is not None and state[:2] == _scope():
        return state[2]
    return current_app.extensions["flaskteroids.i18n"].default_locale


@contextmanager
def with_locale(locale):
    """Select an allowed locale and restore the previous selection on exit."""
    extension = current_app.extensions["flaskteroids.i18n"]
    extension.validate_locale(locale)
    token = _locale.set((*_scope(), locale))
    try:
        yield
    finally:
        _locale.reset(token)


def _key(key, scope):
    if not isinstance(key, str) or not key:
        raise TranslationError("Translation keys must be nonempty strings")
    if scope is not None:
        if not isinstance(scope, str) or not scope:
            raise TranslationError("Translation scope must be a nonempty string")
        key = f"{scope}.{key.lstrip('.')}"
    if any(not part for part in key.split(".")):
        raise TranslationError("Relative keys require a template or explicit scope")
    return key


def _interpolate(text, values, *, html=False):
    def replace(match):
        name = match[1]
        if name not in values:
            raise MissingInterpolationArgument(
                f"Missing interpolation argument: {name}"
            )
        return str(escape(values[name])) if html else str(values[name])

    result = _INTERPOLATION.sub(replace, str(text))
    return Markup(result) if html else result


def translate(
    key, *, locale=None, scope=None, default=_MISSING, count=_MISSING, **values
):
    """Translate a dotted key; Python translations always return ordinary text."""
    return current_app.extensions["flaskteroids.i18n"].translate(
        _key(key, scope), locale=locale, default=default, count=count, values=values
    )


t = translate


def localize(value, *, format="default", locale=None):
    """Format a date/time using named catalog formats or a strftime pattern."""
    extension = current_app.extensions["flaskteroids.i18n"]
    locale = get_locale() if locale is None else locale
    extension.validate_locale(locale)

    def lookup(key):
        result, _ = extension.lookup(locale, key)
        if result is _MISSING:
            raise MissingTranslation(f"translation missing: {locale}.{key}")
        return result

    if not isinstance(format, str) or not format:
        raise TranslationError("A date/time format must be a nonempty string")
    if "%" not in format:
        kind = "time" if isinstance(value, (datetime, time)) else "date"
        format = lookup(f"{kind}.formats.{format}")
    return format_datetime(value, format, lookup)


l = localize  # noqa: E741 - Rails-compatible localization alias.


def reload_translations():
    """Reload this application's catalogs, publishing them only after validation."""
    current_app.extensions["flaskteroids.i18n"].catalog.reload()


@pass_context
def _view_translate(
    context, key, *, scope=None, locale=None, default=_MISSING, count=_MISSING, **values
):
    if isinstance(key, str) and key.startswith(".") and scope is None:
        if not context.name:
            raise TranslationError("Relative translation keys require a named template")
        scope = ".".join(
            part.removeprefix("_") for part in context.name.rsplit(".", 1)[0].split("/")
        )
    key = _key(key, scope)
    last = key.rsplit(".", 1)[-1]
    html = context.eval_ctx.autoescape and (last == "html" or last.endswith("_html"))
    return current_app.extensions["flaskteroids.i18n"].translate(
        key, locale=locale, default=default, count=count, values=values, html=html
    )


class I18nExtension:
    def __init__(self, app):
        config = app.config.i18n
        if not isinstance(config.available_locales, (list, tuple)):
            raise InvalidLocale("available_locales must be a list or tuple")
        self.available_locales = tuple(config.available_locales)
        if not self.available_locales or any(
            not isinstance(locale, str)
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", locale) is None
            for locale in self.available_locales
        ):
            raise InvalidLocale("available_locales must contain locale identifiers")
        self.validate_locale(config.default_locale)
        if not isinstance(config.fallbacks, bool):
            raise TranslationError("i18n.fallbacks must be True or False")
        self.default_locale = config.default_locale
        self.fallbacks = config.fallbacks
        self.raise_on_missing = config.raise_on_missing_translations
        if not isinstance(self.raise_on_missing, bool):
            raise TranslationError(
                "i18n.raise_on_missing_translations must be True or False"
            )
        rules = config.pluralization_rules
        if not callable(getattr(rules, "to_dict", None)):
            raise TranslationError("i18n.pluralization_rules must be a mapping")
        self.pluralization_rules = rules.to_dict()
        if any(
            locale not in self.available_locales or not callable(rule)
            for locale, rule in self.pluralization_rules.items()
        ):
            raise TranslationError(
                "Pluralization rules must map allowed locales to callables"
            )
        self.catalog = Catalog(Path(app.root_path) / app.config.paths.locales)
        app.extensions["flaskteroids.i18n"] = self
        app.jinja_env.globals.update(
            t=_view_translate,
            translate=_view_translate,
            l=localize,
            localize=localize,
            get_locale=get_locale,
        )

    def validate_locale(self, locale):
        if not isinstance(locale, str) or locale not in self.available_locales:
            raise InvalidLocale(f"Unsupported locale: {locale!r}")

    def lookup(self, locale, key):
        result = self.catalog.lookup(locale, key)
        if result is _MISSING and self.fallbacks and locale != self.default_locale:
            return self.catalog.lookup(self.default_locale, key), self.default_locale
        return result, locale

    def translate(
        self,
        key,
        *,
        locale=None,
        default=_MISSING,
        count=_MISSING,
        values=None,
        html=False,
    ):
        locale = get_locale() if locale is None else locale
        self.validate_locale(locale)
        values = dict(values or {})
        if count is not _MISSING:
            if (
                isinstance(count, bool)
                or not isinstance(count, (int, float, Decimal))
                or not Decimal(str(count)).is_finite()
            ):
                raise TranslationError("Translation count must be a finite number")
            values["count"] = count
        result, found_locale = self.lookup(locale, key)
        if result is _MISSING:
            if default is not _MISSING:
                if not isinstance(default, str):
                    raise TranslationError("A translation default must be a string")
                result = default
                # A supplied default is application input, not trusted catalog HTML.
                if html:
                    result = str(escape(result))
            else:
                message = f"translation missing: {locale}.{key}"
                if self.raise_on_missing:
                    raise MissingTranslation(message)
                return message
        if isinstance(result, dict) and count is not _MISSING:
            if count == 0 and "zero" in result:
                category = "zero"
            else:
                rule = self.pluralization_rules.get(found_locale)
                category = rule(count) if rule else ("one" if count == 1 else "other")
            if not isinstance(category, str) or category not in result:
                raise TranslationError(
                    f"Missing plural form {category!r}: {locale}.{key}"
                )
            result = result[category]
        if not isinstance(result, str):
            raise TranslationError(f"Translation must resolve to text: {locale}.{key}")
        return _interpolate(result, values, html=html)
