import pytest

pytestmark = pytest.mark.system


@pytest.mark.parametrize("javascript", ["disabled", "enabled"])
def test_generated_catalog_forms_delete_and_logout_work_in_browser(
    generated_store, javascript
):
    _, run = generated_store
    run(javascript, script="routing_browser.py")
