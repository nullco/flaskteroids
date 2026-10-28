import pytest

from flaskteroids.importmaps import ImportMap, ImportmapError
from flaskteroids.importmaps.configuration import PackagePin, PinFile


@pytest.mark.parametrize(
    "body",
    [
        "    importmap.pin(package)\n",
        '    importmap.pin("a"); importmap.pin("b")\n',
        "    for name in names:\n        importmap.pin(name)\n",
        '    importmap.pin("a", **options)\n',
        '    importmap.pin("a")\n    importmap.pin("a")\n',
        '    if enabled:\n        importmap.pin("a")\n',
        "    return\n",
    ],
)
def test_pin_editor_refuses_ambiguous_configuration(importmap_root, body):
    path = importmap_root / "config/importmap.py"
    path.write_text("def register(importmap):\n" + body)
    before = path.read_bytes()
    with pytest.raises(ImportmapError):
        PinFile(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "source",
    [
        'def register(importmap): importmap.pin("a")\n',
        'def unrelated(importmap):\n    importmap.pin("a")\n',
    ],
)
def test_pin_editor_requires_a_multiline_registration_callback(importmap_root, source):
    path = importmap_root / "config/importmap.py"
    path.write_text(source)
    with pytest.raises(ImportmapError):
        PinFile(path)


def test_pin_editor_keeps_unicode_comments_and_existing_indentation(importmap_root):
    path = importmap_root / "config/importmap.py"
    path.write_text(
        '# café\ndef register(importmap):\n\timportmap.pin("café", preload=False) # préféré\n'
    )
    editor = PinFile(path)
    path.write_text(
        editor.render(
            [
                PackagePin("café", "café.js", "1.2.3"),
                PackagePin("added", "added.js", "2.0.0"),
            ]
        )
    )
    assert "# café" in path.read_text()
    assert "# préféré" in path.read_text()
    pins = {pin.name: pin for pin in ImportMap.load(importmap_root).pins()}
    assert pins["café"].preload is False
    assert pins["added"].to == "added.js"


def test_pin_editor_preserves_code_after_registration(importmap_root):
    path = importmap_root / "config/importmap.py"
    path.write_text(
        'def register(importmap):\n    importmap.pin("application")\n\nSETTING = "preserved"\n'
    )
    path.write_text(PinFile(path).render([PackagePin("added", "added.js", "1.0.0")]))
    assert path.read_text().endswith('SETTING = "preserved"\n')
    assert {pin.name for pin in ImportMap.load(importmap_root).pins()} == {
        "application",
        "added",
    }
