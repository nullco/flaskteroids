class RequestMarker:
    def __init__(self, app, header, *, value):
        self.app = app
        self.header = header
        self.value = value

    def __call__(self, environ, start_response):
        def marked_response(status, headers, exc_info=None):
            return start_response(
                status, [*headers, (self.header, self.value)], exc_info
            )

        return self.app(environ, marked_response)
