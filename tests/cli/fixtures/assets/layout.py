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

response = app.test_client().get(url)
assert response.status_code == 200
assert response.mimetype == "text/css"
assert b"color: rgb(255, 0, 0)" in response.data
assert ("logo-" in response.text) == production
assert ("application-" in url) == production
