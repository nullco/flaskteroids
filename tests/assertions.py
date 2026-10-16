from html.parser import HTMLParser
from xml.etree import ElementTree


class HTML(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.text = ""
        self.feed(str(source))

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

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
