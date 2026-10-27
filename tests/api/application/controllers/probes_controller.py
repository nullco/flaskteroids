from io import BytesIO

from flask import abort, current_app, request, send_file, session

from flaskteroids.controller import ActionController, APIController, wrap_parameters
from flaskteroids.csrf import CSRFToken


class ProbesController(APIController):
    wrap_parameters(False)

    def show(self):
        return self.render(json=dict(self.params))

    def create(self):
        return self.render(json={"method": request.method, "params": dict(self.params)})

    def update(self):
        return self.render(json=dict(self.params))

    def empty(self):
        pass

    def failure(self):
        raise RuntimeError("private implementation detail")

    def conditional(self):
        self.response.set_etag("version")
        response = self.render(json={"message": "stable"})
        return response.make_conditional(request)

    def limited(self):
        abort(429, retry_after=30)

    def download(self):
        return send_file(BytesIO(b"file contents"), mimetype="application/octet-stream")

    def cookie(self):
        session["example"] = True


class WrappedsController(APIController):
    def create(self):
        return self.render(json=dict(self.params))


class CustomWrappedsController(APIController):
    wrap_parameters("payload")

    def create(self):
        return self.render(json=dict(self.params))


class InheritedWrappedsController(CustomWrappedsController):
    pass


class DisabledWrappedsController(CustomWrappedsController):
    wrap_parameters(False)


class RestoredWrappedsController(DisabledWrappedsController):
    wrap_parameters(True)


class EnvelopeWrapping:
    wrap_parameters("envelope")


class MixinWrappedsController(EnvelopeWrapping, WrappedsController):
    pass


class OverriddenWrappedsController(WrappedsController):
    wrap_parameters(False)
    wrap_parameters("final")


class BrowserWrappedsController(ActionController):
    wrap_parameters("browser")

    def create(self):
        return self.render(json=dict(self.params))


class BrowserController(ActionController):
    def show(self):
        return self.render(
            json={"csrf_token": CSRFToken(current_app.secret_key).generate()}
        )

    def create(self):
        return self.render(json={"saved": True})
