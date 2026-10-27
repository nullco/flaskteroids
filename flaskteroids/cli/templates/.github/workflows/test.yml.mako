name: Test

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --locked
      - run: bin/flask test
<%block name="browser_tests">      - run: .venv/bin/playwright install --with-deps chromium
      - run: bin/flask test:system
</%block>\
