"""Controller-family HTTP policies, independent of application composition."""

from flask import current_app, request

from flaskteroids.csrf import CSRFToken


class BrowserRequestPolicy:
    def protect(self):
        CSRFToken(current_app.secret_key).validate()

    def error_response(self, error):
        return error.get_response(request.environ)


class APIRequestPolicy:
    def protect(self):
        pass

    def error_response(self, error):
        response = error.get_response(request.environ)
        if error.code is not None:
            response.set_data(
                current_app.json.dumps(
                    {
                        "error": error.name,
                        "status": error.code,
                    }
                )
            )
            response.mimetype = "application/json"
        return response


BROWSER_REQUESTS = BrowserRequestPolicy()
API_REQUESTS = APIRequestPolicy()


def request_policy(default):
    view = current_app.view_functions.get(request.endpoint)
    return getattr(view, "_flaskteroids_request_policy", default)
