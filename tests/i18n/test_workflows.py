import json

import pytest
from jinja2 import DictLoader

from flaskteroids.i18n import get_locale, with_locale
from flaskteroids.mailer import MessageDeliveryJob
from tests.assertions import HTML
from tests.i18n.fixtures.mailers.notices_mailer import NoticesMailer


def test_controller_views_and_partials_use_the_request_locale(localized_app):
    client = localized_app.test_client()
    response = client.get("/products/?locale=es")
    assert response.status_code == 200
    assert "Productos" in HTML(response.text).text
    assert "Fila de producto" in HTML(response.text).text
    assert "Products" in HTML(client.get("/products/").text).text


def test_controller_relative_translation_uses_its_action_scope(localized_app):
    response = localized_app.test_client().get("/products/show/?locale=es")
    assert response.status_code == 200
    assert response.json == {"notice": "Producto encontrado"}


def test_request_locale_restores_after_errors_and_redirects(localized_app):
    client = localized_app.test_client()
    with localized_app.app_context(), with_locale("ru"):
        with pytest.raises(RuntimeError, match="Locale scope failed"):
            client.get("/products/fail/?locale=es")
        assert get_locale() == "ru"
        assert client.get("/products/redirect/?locale=es").status_code == 302
        assert get_locale() == "ru"
        assert "Products" in HTML(client.get("/products/").text).text


def test_invalid_request_locale_returns_bad_request(localized_app):
    client = localized_app.test_client()
    assert client.get("/products/?locale=../../es").status_code == 400
    assert "Products" in HTML(client.get("/products/").text).text


@pytest.mark.parametrize("queued", [False, True])
def test_mail_captures_composition_locale_for_later_rendering(localized_app, queued):
    with localized_app.app_context():
        with with_locale("es"):
            delivery = NoticesMailer().welcome("<Ana>")
        if queued:
            delivery.deliver_later()
            localized_app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        else:
            delivery.deliver_now()
        assert get_locale() == "en"
        messages = localized_app.extensions[
            "flaskteroids.mail"
        ].delivery_method.deliveries
        message = messages[-1]
        assert message["Subject"] == "Bienvenido <Ana>"
        assert (
            "Bienvenido <Ana>"
            in message.get_body(preferencelist=("plain",)).get_content()
        )
        html = message.get_body(preferencelist=("html",)).get_content()
        assert "Bienvenido &lt;Ana&gt;" in html
        assert "<b>&lt;Ana&gt;</b>" in html


def test_queued_mail_restores_serialized_locale_in_a_fresh_execution_context(
    localized_app,
):
    queue = localized_app.extensions["flaskteroids.jobs"].queue_adapter
    with localized_app.app_context(), with_locale("es"):
        NoticesMailer().welcome("Ana").deliver_later()
        payload = json.loads(json.dumps(queue.enqueued_jobs[0].kwargs))
        queue.clear()
    with localized_app.app_context(), with_locale("ru"):
        MessageDeliveryJob().perform(**payload)
        assert get_locale() == "ru"
        messages = localized_app.extensions[
            "flaskteroids.mail"
        ].delivery_method.deliveries
        assert (
            "Bienvenido Ana"
            in messages[-1].get_body(preferencelist=("plain",)).get_content()
        )


def test_mail_template_failure_restores_the_delivery_locale(localized_app):
    localized_app.jinja_env.globals["fail"] = lambda: 1 / 0
    localized_app.jinja_loader = DictLoader(
        {"notices_mailer/welcome.html": "{{ fail() }}"}
    )
    with localized_app.app_context():
        with with_locale("es"):
            delivery = NoticesMailer().welcome("Ana")
        with pytest.raises(ZeroDivisionError):
            delivery.deliver_now()
        assert get_locale() == "en"
