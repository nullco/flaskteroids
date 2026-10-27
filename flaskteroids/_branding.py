from base64 import b64encode
from importlib.resources import files


def brand_images(*names):
    assets = files("flaskteroids").joinpath("controllers/templates/brand")
    return {
        name: "data:image/svg+xml;base64,"
        + b64encode(assets.joinpath(f"{name}.svg").read_bytes()).decode("ascii")
        for name in names
    }
