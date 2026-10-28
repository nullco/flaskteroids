import pytest

from flaskteroids.importmaps.installation import install
from flaskteroids.importmaps.packages import HTTPClient


@pytest.fixture
def importmap_root(tmp_path):
    install(tmp_path)
    return tmp_path


@pytest.fixture
def package_client(mocker):
    client = mocker.Mock(spec=HTTPClient)
    client.json.return_value = {
        "map": {
            "imports": {
                "library": "https://ga.jspm.io/npm:library@1.2.3/index.js",
                "dependency": "https://ga.jspm.io/npm:dependency@2.0.0/index.js",
            }
        },
    }
    client.request.return_value = (
        b"export const value = 42;\n//# sourceMappingURL=index.js.map\n"
    )
    return client
