from datetime import UTC, date, datetime, time, timedelta, timezone

import pytest
from flask import render_template_string

from flaskteroids.i18n import (
    MissingTranslation,
    TranslationError,
    localize,
    with_locale,
)
from flaskteroids.i18n import l as localize_short


@pytest.mark.parametrize(
    "value, expected",
    [
        (date(2026, 3, 2), "2026-03-02"),
        (
            datetime(2026, 3, 2, 13, 5, tzinfo=UTC),
            "Mon, 02 Mar 2026 13:05:00 +0000",
        ),
    ],
)
def test_english_formats_work_without_application_date_catalogs(
    localized_app, value, expected
):
    with localized_app.app_context():
        assert localize(value) == expected


def test_catalog_formats_translate_month_and_day_names(localized_app):
    with localized_app.app_context(), with_locale("es"):
        assert localize(date(2026, 3, 2)) == "02/03/2026"
        assert localize(date(2026, 3, 2), format="long") == "lunes, 2 de marzo de 2026"
        assert localize(date(2026, 3, 1), format="%a %b") == "dom mar"
        assert localize_short(time(13, 5), format="short") == "13:05"
        assert (
            render_template_string(
                '{{ l(value, format="long") }}', value=date(2026, 3, 2)
            )
            == "lunes, 2 de marzo de 2026"
        )


def test_date_formatting_uses_catalog_names_instead_of_process_locale(
    localized_app, mocker
):
    mocker.patch(
        "locale.setlocale", side_effect=AssertionError("Global locale changed")
    )
    with localized_app.app_context():
        assert localize(date(2026, 3, 2), format="%A %B", locale="es") == "lunes marzo"
        assert localize(date(2026, 3, 2), format="%A %B", locale="en") == "Monday March"


def test_datetime_formatting_preserves_timezone_and_literal_percent(localized_app):
    value = datetime(2026, 3, 2, 13, 5, 6, 123, tzinfo=timezone(timedelta(hours=2)))
    with localized_app.app_context():
        assert (
            localize(value, format="%Y-%m-%d %H:%M:%S.%f %z %% %p", locale="es")
            == "2026-03-02 13:05:06.000123 +0200 % P. M."
        )
        assert localize(value, format="%%A") == "%A"


@pytest.mark.parametrize("pattern", ["%c", "%x", "%X", "%Q", "%", "text%"])
def test_date_formatting_rejects_unsupported_or_incomplete_directives(
    localized_app, pattern
):
    with localized_app.app_context(), pytest.raises(TranslationError):
        localize(date(2026, 3, 2), format=pattern)


def test_missing_date_names_and_formats_raise_diagnostic_errors(localized_app):
    with localized_app.app_context():
        with pytest.raises(MissingTranslation, match="ru.date.formats.default"):
            localize(date(2026, 3, 2), locale="ru")
        with pytest.raises(MissingTranslation, match="ru.date.month_names"):
            localize(date(2026, 3, 2), format="%B", locale="ru")


def test_date_formatting_rejects_unsupported_values(localized_app):
    with localized_app.app_context(), pytest.raises(TypeError):
        localize("2026-03-02")
