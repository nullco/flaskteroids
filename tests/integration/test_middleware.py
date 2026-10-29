from pathlib import Path
from shutil import copyfile

import pytest


@pytest.mark.parametrize("api_only", [False, True])
def test_generated_application_configures_and_inspects_wsgi_middleware(
    generated_app_factory, api_only
):
    options = ("--api",) if api_only else ()
    root, run = generated_app_factory("middleware_app", *options)
    source = Path(__file__).parent / "application/middleware"
    for path in source.rglob("*.py"):
        destination = root / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(path, destination)

    result = run("middleware")
    entries = result.stdout.splitlines()
    assert "use app.middleware.request_marker.RequestMarker" in entries
    assert "use werkzeug.middleware.proxy_fix.ProxyFix" not in entries
    assert any("MethodOverrideMiddleware" in entry for entry in entries) is not api_only
    run(script="middleware.py")
