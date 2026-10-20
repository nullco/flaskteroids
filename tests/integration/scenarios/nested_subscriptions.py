from app.models.product import Product
from app.models.subscriber import Subscriber
from wsgi import app

from tests.assertions import HTML
from tests.integration.scenarios.routing_support import account, sign_in, submit_form

with account(app) as user:
    client = app.test_client()
    sign_in(client, user)
    with app.app_context():
        product = Product.create(name="Nested forms", quantity=0)
        product_id = product.id
    try:
        collection = f"/products/{product_id}/subscribers"
        new = client.get(collection + "/new")
        assert new.status_code == 200
        html = HTML(new.text)
        assert html.has("input", name="subscriber[email]", value="")
        rejected = submit_form(
            client, new, collection, **{"subscriber[email]": "a@b.c"}
        )
        assert rejected.status_code == 422
        html = HTML(rejected.text)
        assert html.has("input", name="subscriber[email]", value="a@b.c")
        assert html.has("ul", id="errors")
        assert html.has("form", action=collection)
        with app.app_context():
            assert Subscriber.where(product_id=product_id).count() == 0
        created = submit_form(
            client, rejected, collection, **{"subscriber[email]": "reader@example.com"}
        )
        assert created.status_code == 302
        with app.app_context():
            subscriber = Subscriber.find_by(product_id=product_id)
            assert subscriber.email == "reader@example.com"
            subscriber_id = subscriber.id
        member = f"{collection}/{subscriber_id}"
        edit = client.get(member + "/edit")
        assert edit.status_code == 200
        html = HTML(edit.text)
        assert html.has("input", name="_method", value="PATCH")
        assert html.has("input", name="subscriber[email]", value="reader@example.com")
        updated = submit_form(
            client, edit, member, **{"subscriber[email]": "changed@example.com"}
        )
        assert updated.status_code == 302
        with app.app_context():
            assert Subscriber.find(subscriber_id).email == "changed@example.com"

        product_edit = client.get(f"/products/{product_id}/edit")
        invalid_product = submit_form(
            client,
            product_edit,
            f"/products/{product_id}",
            **{"product[quantity]": "12garbage"},
        )
        assert invalid_product.status_code == 422
        assert HTML(invalid_product.text).has(
            "input", name="product[quantity]", value="12garbage"
        )
    finally:
        with app.app_context():
            Product.find(product_id).destroy()
