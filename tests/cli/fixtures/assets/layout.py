import sys

from flask import render_template
from wsgi import app

from flaskteroids.helpers import asset_path

production = sys.argv[1] == "production"

with app.test_request_context():
    html = render_template("layouts/application.html")
    url = asset_path("application.css")
    assert f'href="{url}"' in html
    assert 'data-turbo-track="reload"' in html
    turbo_url = asset_path("turbo/turbo.js")
    assert f'src="{turbo_url}"' in html

response = app.test_client().get(url)
assert response.status_code == 200
assert response.mimetype == "text/css"
assert b"color: rgb(255, 0, 0)" in response.data
assert ("logo-" in response.text) == production
assert ("application-" in url) == production

runtime = app.test_client().get(turbo_url)
assert runtime.status_code == 200
assert runtime.mimetype in {"application/javascript", "text/javascript"}
assert b"Turbo 8.0.23" in runtime.data
assert ("turbo-" in turbo_url) == production
