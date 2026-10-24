import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from flask import render_template_string
from jinja2 import DictLoader
from markupsafe import Markup

from flaskteroids.i18n import (
    InvalidLocale,
    MissingInterpolationArgument,
    MissingTranslation,
    TranslationError,
    get_locale,
    reload_translations,
    t,
    translate,
    with_locale,
)


def test_translations_use_application_default_and_explicit_locale(i18n_app_factory):
    app = i18n_app_factory(default_locale="es")
    with app.app_context():
        assert get_locale() == "es"
        assert t("hello", name="Ana") == "Hola Ana"
        assert translate("hello", name="Ann", locale="en") == "Hello Ann"
        assert get_locale() == "es"


def test_scoped_locale_restores_after_nested_scopes_and_errors(localized_app):
    with localized_app.app_context():
        with with_locale("es"):
            assert get_locale() == "es"
            with pytest.raises(RuntimeError), with_locale("ru"):
                assert get_locale() == "ru"
                raise RuntimeError("Interrupted translation")
            assert get_locale() == "es"
        assert get_locale() == "en"


def test_locale_and_catalogs_are_application_local(i18n_app_factory):
    first = i18n_app_factory("first")
    second = i18n_app_factory("second", default_locale="ru")
    path = second.project_root / "config/locales/en.yml"
    path.write_text('en:\n  hello: "Second %{name}"\n')
    with first.app_context(), with_locale("es"):
        with second.app_context():
            assert get_locale() == "ru"
            assert t("hello", locale="en", name="app") == "Second app"
        assert get_locale() == "es"
        assert t("hello", locale="en", name="app") == "Hello app"
    with first.app_context():
        assert get_locale() == "en"


def test_nested_requests_start_with_their_own_default_locale(localized_app):
    with localized_app.app_context(), with_locale("ru"):
        with localized_app.test_request_context():
            assert get_locale() == "en"
            with with_locale("es"):
                with localized_app.test_request_context():
                    assert get_locale() == "en"
                assert get_locale() == "es"
        assert get_locale() == "ru"


def test_concurrent_requests_keep_independent_locales(localized_app):
    barrier = Barrier(2)

    def render(locale):
        with localized_app.test_request_context(), with_locale(locale):
            barrier.wait(timeout=5)
            return t("hello", name="Ana")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(render, locale) for locale in ("en", "es")]
        assert [future.result(timeout=10) for future in futures] == [
            "Hello Ana",
            "Hola Ana",
        ]


def test_concurrent_tasks_share_request_context_but_keep_independent_locales(
    localized_app,
):
    async def render(locale):
        with with_locale(locale):
            await asyncio.sleep(0)
            return t("hello", name="Ana")

    async def run():
        return await asyncio.gather(render("en"), render("es"))

    with localized_app.test_request_context():
        assert asyncio.run(run()) == ["Hello Ana", "Hola Ana"]
        assert get_locale() == "en"


@pytest.mark.parametrize("locale", ["../es", "de", "", None, ["es"]])
def test_locale_selection_rejects_values_outside_allowlist(localized_app, locale):
    with localized_app.app_context():
        with pytest.raises(InvalidLocale), with_locale(locale):
            pytest.fail("Unsupported locale entered its scope")
        if locale is not None:
            with pytest.raises(InvalidLocale):
                t("hello", locale=locale)
        assert get_locale() == "en"


@pytest.mark.parametrize(
    "settings",
    [
        {"default_locale": "de"},
        {"available_locales": ["../en"]},
        {"available_locales": []},
        {"available_locales": "en"},
        {"available_locales": None},
        {"raise_on_missing_translations": "yes"},
        {"pluralization_rules": None},
        {"fallbacks": ["en"]},
        {"pluralization_rules": {"es": "not callable"}},
        {"pluralization_rules": {"de": lambda count: "other"}},
    ],
)
def test_invalid_locale_configuration_rejects_application_boot(
    i18n_app_factory, settings
):
    with pytest.raises(TranslationError):
        i18n_app_factory(**settings)


def test_missing_translations_have_diagnostic_text_and_explicit_defaults(localized_app):
    with localized_app.app_context():
        assert t("absent") == "translation missing: en.absent"
        assert t("absent", default="Hello %{name}", name="Ana") == "Hello Ana"


def test_strict_missing_translation_policy_raises(i18n_app_factory):
    app = i18n_app_factory(raise_on_missing_translations=True)
    with app.app_context(), pytest.raises(MissingTranslation, match="en.absent"):
        t("absent")


@pytest.mark.parametrize(
    "fallbacks, expected",
    [(False, "translation missing: es.english_only"), (True, "English fallback")],
)
def test_default_locale_fallback_is_explicit(i18n_app_factory, fallbacks, expected):
    app = i18n_app_factory(fallbacks=fallbacks)
    with app.app_context(), with_locale("es"):
        assert t("english_only") == expected


def test_interpolation_preserves_plain_text_and_reports_missing_arguments(
    localized_app,
):
    with localized_app.app_context():
        assert t("hello", name="<Ana>") == "Hello <Ana>"
        assert t("hello", name="%{another}") == "Hello %{another}"
        assert t("index.title", scope="products") == "Products"
        with pytest.raises(MissingInterpolationArgument, match="name"):
            t("hello")
        with pytest.raises(TranslationError):
            t(".title")


@pytest.mark.parametrize(
    "count, expected",
    [
        (0, "No messages"),
        (1, "One message"),
        (2, "2 messages"),
        (Decimal("1.0"), "One message"),
    ],
)
def test_basic_pluralization_selects_zero_one_and_other(localized_app, count, expected):
    with localized_app.app_context():
        assert t("messages", count=count) == expected


@pytest.mark.parametrize(
    "count, expected",
    [
        (1, "1 сообщение"),
        (2, "2 сообщения"),
        (5, "5 сообщений"),
        (11, "11 сообщений"),
        (21, "21 сообщение"),
    ],
)
def test_locale_specific_plural_rule_selects_catalog_forms(
    localized_app, count, expected
):
    with localized_app.app_context():
        assert t("messages", locale="ru", count=count) == expected


@pytest.mark.parametrize(
    "count", [True, "2", float("inf"), float("nan"), Decimal("NaN"), None]
)
def test_pluralization_rejects_invalid_counts(localized_app, count):
    with localized_app.app_context(), pytest.raises(TranslationError):
        t("messages", count=count)


def test_explicit_zero_form_takes_precedence_over_the_locale_rule(i18n_app_factory):
    def positive_plural(count):
        if count == 0:
            raise AssertionError("The zero form already handles this count")
        return "other"

    app = i18n_app_factory(pluralization_rules={"es": positive_plural})
    with app.app_context():
        assert t("messages", locale="es", count=0) == "Ningún mensaje"


def test_pluralization_rejects_missing_forms(localized_app):
    with localized_app.app_context(), pytest.raises(TranslationError, match="other"):
        t("incomplete", count=2)


def test_fallback_pluralization_uses_the_catalogs_rule(i18n_app_factory):
    app = i18n_app_factory(fallbacks=True)
    path = app.project_root / "config/locales/nested/ru.yaml"
    path.unlink()
    with app.app_context():
        assert t("messages", locale="ru", count=2) == "2 messages"


def test_template_translations_escape_text_and_html_interpolations(localized_app):
    with localized_app.app_context():
        assert (
            render_template_string('{{ t("plain", name=name) }}', name="<Ana>")
            == "&lt;b&gt;&lt;Ana&gt;&lt;/b&gt;"
        )
        for key in ("welcome_html", "notice.html"):
            html = render_template_string(
                "{{ translate(key, name=name) }}", key=key, name="<Ana>"
            )
            assert "&lt;Ana&gt;" in html
            assert "<Ana>" not in html
            assert "&lt;b&gt;" not in html
        assert (
            render_template_string(
                '{{ t("welcome_html", name=name) }}', name=Markup("<i>Ana</i>")
            )
            == "<b><i>Ana</i></b>"
        )
        assert type(t("welcome_html", name="<Ana>")) is str


def test_html_translation_defaults_are_escaped(localized_app):
    with localized_app.app_context():
        assert (
            render_template_string(
                '{{ t("absent_html", default=value) }}', value="<script>bad()</script>"
            )
            == "&lt;script&gt;bad()&lt;/script&gt;"
        )


def test_text_templates_preserve_text_without_html_escaping(localized_app):
    localized_app.jinja_loader = DictLoader(
        {"notice.txt": '{{ t("welcome_html", name=name) }}'}
    )
    with localized_app.app_context():
        assert (
            localized_app.jinja_env.get_template("notice.txt").render(name="<Ana>")
            == "<b><Ana></b>"
        )


def test_catalog_reload_merges_nested_files_and_replaces_published_data(localized_app):
    path = localized_app.project_root / "config/locales/z_extra.yaml"
    with localized_app.app_context():
        assert t("hello", name="Ana") == "Hello Ana"
        path.write_text(
            'en:\n  hello: "Hi %{name}"\n  products:\n    index:\n      other: "Extra"\n'
        )
        assert t("hello", name="Ana") == "Hello Ana"
        reload_translations()
        assert t("hello", name="Ana") == "Hi Ana"
        assert t("products.index.title") == "Products"
        assert t("products.index.other") == "Extra"


@pytest.mark.parametrize(
    "source",
    [
        "[invalid",
        "- a list",
        "en: text",
        "en:\n  on: text",
        'en:\n  unsafe: !!python/object/apply:builtins.eval ["1+1"]',
        "en: &cycle\n  cycle: *cycle",
    ],
)
def test_invalid_catalog_reload_preserves_the_previous_catalog(localized_app, source):
    path = localized_app.project_root / "config/locales/z_invalid.yml"
    with localized_app.app_context():
        assert t("hello", name="Ana") == "Hello Ana"
        path.write_text(source)
        with pytest.raises(TranslationError):
            reload_translations()
        assert t("hello", name="Ana") == "Hello Ana"


def test_catalogs_allow_application_defined_locale_identifiers(i18n_app_factory):
    app = i18n_app_factory(available_locales=["en", "x-pirate"], pluralization_rules={})
    path = app.project_root / "config/locales/pirate.yml"
    path.write_text('x-pirate:\n  hello: "Ahoy %{name}"\n')
    with app.app_context(), with_locale("x-pirate"):
        assert t("hello", name="Ana") == "Ahoy Ana"
