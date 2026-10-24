from wsgi import app

from flaskteroids.i18n import get_locale, t, with_locale
from tests.assertions import HTML

with app.app_context():
    assert t("hello") == "Hello world"
    with with_locale("es"):
        assert t("catalog.index.title") == "Catálogo"
    assert get_locale() == "en"

client = app.test_client()
spanish = client.get("/catalog/?locale=es")
assert spanish.status_code == 200
assert "Catálogo" in HTML(spanish.text).text
assert HTML(spanish.text).has("html", lang="es")
assert HTML(spanish.text).has("a", href="/catalog/?locale=es")
assert client.get("/catalog/show/?locale=es").json == {"notice": "Producto encontrado"}
assert "Catalog" in HTML(client.get("/catalog/").text).text
assert client.get("/catalog/?locale=../../es").status_code == 400
