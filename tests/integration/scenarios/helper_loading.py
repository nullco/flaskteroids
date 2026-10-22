"""Verify helper discovery in a freshly booted application process."""

import sys

from flask import render_template_string
from wsgi import app

from tests.assertions import HTML

name, notice = sys.argv[1:]
with app.app_context():
    output = render_template_string(
        "{{ application_name() }}|{{ notice() if notice is defined else '-' }}"
    )
    assert output == f"{name}|{notice}", output

response = app.test_client().get("/catalog")
assert response.status_code == 200, response.text
assert f"Browse {name}" in HTML(response.text).text
