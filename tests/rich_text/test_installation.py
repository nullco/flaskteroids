from flaskteroids.importmaps import ImportMap
from flaskteroids.importmaps.configuration import PinFile
from flaskteroids.rich_text.installation import install_javascript


def test_install_configures_packaged_modules_without_copying_runtimes(tmp_path):
    install_javascript(tmp_path)
    pins = {pin.name: pin.to for pin in ImportMap.load(tmp_path).pins()}
    assert pins["lexxy"] == "lexxy.js"
    assert pins["flaskteroids/rich-text"] == "rich_text.js"
    assert pins["@rails/activestorage"] == "rich_text_uploads.js"
    assert PinFile(tmp_path / "config/importmap.py").packages() == ()
    assert (
        'import "flaskteroids/rich-text"'
        in (tmp_path / "app/javascript/application.js").read_text()
    )
    assert not (tmp_path / "app/assets").exists()
    assert install_javascript(tmp_path).files == ()


def test_install_preserves_application_configuration_and_javascript(tmp_path):
    config = tmp_path / "config/importmap.py"
    config.parent.mkdir()
    original = (
        "def register(modules):\n"
        '    modules.pin("lexxy", to="https://cdn.example/lexxy.js", preload=False)\n'
        "\nSETTING = True\n"
    )
    config.write_text(original)
    entrypoint = tmp_path / "app/javascript/application.js"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_text('window.applicationCode = "preserved"\n')
    install_javascript(tmp_path)
    pin = next(pin for pin in ImportMap.load(tmp_path).pins() if pin.name == "lexxy")
    assert pin.to == "https://cdn.example/lexxy.js"
    assert pin.preload is False
    assert config.read_text().endswith("SETTING = True\n")
    assert entrypoint.read_text().startswith('window.applicationCode = "preserved"\n')
    assert install_javascript(tmp_path).files == ()


def test_install_reports_dynamic_pin_configuration_without_rewriting_it(tmp_path):
    config = tmp_path / "config/importmap.py"
    config.parent.mkdir()
    original = (
        "def register(modules):\n"
        '    for name in ["application"]:\n'
        "        modules.pin(name)\n"
    )
    config.write_text(original)
    result = install_javascript(tmp_path)
    assert config.read_text() == original
    assert any(
        "Configure rich-text pins manually" in item for item in result.instructions
    )
