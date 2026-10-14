import re

_STRING = r"""(?:"(?:\\[\s\S]|[^"\\\n\r\f])*"|'(?:\\[\s\S]|[^'\\\n\r\f])*')"""
_REFERENCES = re.compile(
    rf"(?P<comment>/\*.*?\*/)"
    rf"|(?P<import>@import(?:\s|/\*.*?\*/)+(?P<import_value>{_STRING}))"
    rf"""|(?P<url>(?<![-\w\\])url\(\s*(?P<url_value>{_STRING}|(?:\\[\s\S]|[^\\\s'"()])*?)\s*\))"""
    rf"|(?P<string>{_STRING})",
    re.IGNORECASE | re.DOTALL,
)
_ESCAPE = re.compile(
    r"\\(?:([0-9a-f]{1,6})(?:\r\n|[ \t\n\r\f])?|(\r\n|[\n\r\f])|(.))",
    re.IGNORECASE | re.DOTALL,
)


def _unescape(value):
    def replace(match):
        if match[1]:
            codepoint = int(match[1], 16)
            return (
                chr(codepoint)
                if 0 < codepoint <= 0x10FFFF and not 0xD800 <= codepoint <= 0xDFFF
                else "\ufffd"
            )
        return "" if match[2] else match[3]

    return _ESCAPE.sub(replace, value)


def _quote(value):
    def replace(match):
        character = match[0]
        return (
            "\\" + character if character in ('"', "\\") else f"\\{ord(character):x} "
        )

    return '"' + re.sub(r'["\\\x00-\x1f\x7f]', replace, value) + '"'


def rewrite_urls(data, resolve):
    """Rewrite standard url(...) and quoted @import references, not arbitrary CSS."""

    def replace(match):
        group = "url_value" if match.group("url") else "import_value"
        value = match.group(group)
        if value is None:
            return match[0]
        raw = value[1:-1] if value.startswith(('"', "'")) else value
        original = _unescape(raw)
        rewritten = resolve(original)
        if rewritten == original:
            return match[0]
        start = match.start(group) - match.start()
        end = match.end(group) - match.start()
        return match[0][:start] + _quote(rewritten) + match[0][end:]

    return _REFERENCES.sub(replace, data.decode("utf-8")).encode("utf-8")
