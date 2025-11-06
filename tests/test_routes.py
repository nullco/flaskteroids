import pytest


@pytest.fixture
def app(app, mocker):
    mocker.patch.object(app, 'add_url_rule')
    return app


@pytest.fixture
def router(app):
    return app.extensions["flaskteroids.routes"]


class TestRoutes:

    def test_root_registers_route(self, router, app, mocker):
        router.root(to="welcome#index")
        app.add_url_rule.assert_called_with('/', view_func=mocker.ANY, methods=['GET'])

    def test_get_registers_route(self, router, app, mocker):
        router.get("/test", to="test#index")
        app.add_url_rule.assert_called_with('/test', view_func=mocker.ANY, methods=['GET'])

    def test_post_registers_route(self, router, app, mocker):
        router.post("/test", to="test#create")
        app.add_url_rule.assert_called_with('/test', view_func=mocker.ANY, methods=['POST'])

    def test_put_registers_route(self, router, app, mocker):
        router.put("/test", to="test#update")
        app.add_url_rule.assert_called_with('/test', view_func=mocker.ANY, methods=['PUT'])

    def test_delete_registers_route(self, router, app, mocker):
        router.delete("/test", to="test#destroy")
        app.add_url_rule.assert_called_with('/test', view_func=mocker.ANY, methods=['DELETE'])

    def test_resources_registers_multiple_routes(self, router, app):
        router.resources("posts")
        assert app.add_url_rule.call_count == 12

    def test_resource_registers_singular_routes(self, router, app):
        router.resource("profile")
        assert app.add_url_rule.call_count == 6

    def test_has_path_returns_true_for_registered_path(self, router):
        router.get("/test", to="test#index")
        assert router.has_path("/test") is True
        assert router.has_path("/notfound") is False
