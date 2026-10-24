import shutil
from pathlib import Path


def test_generated_application_loads_catalogs_and_scopes_locales(generated_app_factory):
    root, run = generated_app_factory("localized")
    source = Path(__file__).parent / "application/localized"
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            destination = root / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
    run(script="localization.py")
