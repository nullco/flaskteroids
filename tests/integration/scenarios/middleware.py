from app.middleware.request_marker import RequestMarker
from flask import request
from wsgi import app


@app.get("/middleware-probe")
def probe():
    return {"address": request.remote_addr}


assert app.middleware[-1].klass is RequestMarker
response = app.test_client().get(
    "/middleware-probe", headers={"X-Forwarded-For": "198.51.100.7"}
)
assert response.status_code == 200
assert response.headers["X-Application"] == "middleware-test"
assert response.json == {"address": "127.0.0.1"}
