"""Install application-owned copies of the supported upstream browser runtime."""

from importlib.resources import files

ASSET_NAMES = ("turbo.js", "TURBO-LICENSE", "README.md")
SCRIPT_TAG = (
    "<script defer src=\"{{ asset_path('turbo/turbo.js') }}\" "
    'data-turbo-track="reload"></script>'
)


def install_assets(root, *, source_path="app/assets", force=False):
    destination = root / source_path / "turbo"
    destination.mkdir(parents=True, exist_ok=True)
    resources = files("flaskteroids.turbo").joinpath("assets")
    created = []
    for name in ASSET_NAMES:
        target = destination / name
        if force or not target.exists():
            target.write_bytes(resources.joinpath(name).read_bytes())
            created.append(target)
    return created
