import unicodedata
from urllib.parse import quote

from werkzeug.http import dump_options_header


def sanitize_filename(filename):
    filename = filename.replace("\\", "/").split("/")[-1].strip()
    unsafe = '%$|:;/<>?*"\u202e'
    return (
        "".join(
            "-"
            if character in unsafe or ord(character) < 32 or ord(character) == 127
            else character
            for character in filename
        )
        or "file"
    )


def content_disposition(filename, disposition):
    filename = sanitize_filename(filename)
    try:
        filename.encode("ascii")
        options = {"filename": filename}
    except UnicodeEncodeError:
        fallback = (
            unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
            or "file"
        )
        options = {
            "filename": fallback,
            "filename*": "UTF-8''" + quote(filename, safe=""),
        }
    return dump_options_header(disposition, options)
