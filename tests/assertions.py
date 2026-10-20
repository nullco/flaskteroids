from html.parser import HTMLParser
from xml.etree import ElementTree


class HTML(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.forms = []
        self._form = None
        self.text = ""
        self.feed(str(source))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if tag == "form":
            self._form = {"attributes": attrs, "fields": {}}
            self.forms.append(self._form)
        elif tag == "input" and self._form is not None and "name" in attrs:
            self._form["fields"][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None

    def handle_data(self, data):
        self.text += data

    def has(self, tag, **attributes):
        return any(
            name == tag and attributes.items() <= attrs.items()
            for name, attrs in self.elements
        )


def assert_pytest_passed(report):
    results = ElementTree.parse(report).getroot()
    assert results.findall(".//testcase"), "The test run did not execute any tests"
    for outcome in ("failure", "error", "skipped"):
        assert not results.findall(f".//{outcome}"), f"Unexpected {outcome} in {report}"
