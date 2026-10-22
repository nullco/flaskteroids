import pytest

from flaskteroids import cache
from flaskteroids.cache import MISSING
from flaskteroids.cache.factory import get_cache
from flaskteroids.controller import ActionController, init
from flaskteroids.rate_limit import rate_limit


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_cache_values_counters_and_expiry_are_app_local(make_app, mocker, order):
    clock = mocker.patch("flaskteroids.cache.inmemory.time.time", return_value=100)
    apps = {name: make_app(name) for name in order}
    key = "isolated-key"
    cache.store(key, "standalone")
    for name in ("a", "b"):
        with apps[name].app_context():
            assert cache.fetch(key) is MISSING
            cache.store(key, name, ttl=10 if name == "a" else 20)
            assert cache.increment("counter") == 1
    with apps["a"].app_context():
        assert cache.fetch(key) == "a"
        assert get_cache().increment("counter") == 2
        with apps["b"].app_context():
            assert cache.fetch(key) == "b"
            assert cache.increment("counter") == 2
        assert cache.fetch(key) == "a"
    clock.return_value = 111
    with apps["a"].app_context():
        assert cache.fetch(key) is MISSING
    with apps["b"].app_context():
        assert cache.fetch(key) == "b"
    assert cache.fetch(key) == "standalone"


def test_rate_limits_are_app_local(make_app):
    class LimitedController(ActionController):
        rate_limit(to=2, within=60)

        def index(self):
            return "ok"

    init(LimitedController)
    a, b = make_app("a"), make_app("b")
    for app in (a, b):
        app.add_url_rule("/limited/", view_func=lambda: LimitedController().index())
    client_a, client_b = a.test_client(), b.test_client()
    assert client_a.get("/limited/").status_code == 200
    assert client_a.get("/limited/").status_code == 200
    assert client_a.get("/limited/").status_code == 429
    assert client_b.get("/limited/").status_code == 200
    assert client_a.get("/limited/").status_code == 429
