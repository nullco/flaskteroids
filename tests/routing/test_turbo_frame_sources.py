import pytest

from flaskteroids.turbo import turbo_frame_tag
from tests.assertions import HTML
from tests.routing.app.models.records import Product, Subscriber


def test_frame_sources_accept_model_destinations(routing_app):
    with routing_app.test_request_context():
        product = Product.create(name="Frame source")
        subscriber = Subscriber.new()
        assert HTML(turbo_frame_tag("preview", src=product)).has(
            "turbo-frame", src=f"/products/{product.id}"
        )
        assert HTML(turbo_frame_tag("subscribers", src=[product, subscriber])).has(
            "turbo-frame", src=f"/products/{product.id}/subscribers"
        )


@pytest.mark.parametrize("identifiers", [("tray", 1), (["tray", 1],), (("tray", 1),)])
def test_frame_ids_join_compound_identifiers(identifiers):
    assert HTML(turbo_frame_tag(*identifiers)).has("turbo-frame", id="tray_1")
