from test.test_helper import SystemTest
from flaskteroids.routes import ${collection}_path


class ${controller}Test(SystemTest):
    fixtures = ["${plural}"]

    def setup(self):
        self.${singular} = self.${plural}("one")

    def test_visiting_the_index(self):
        self.visit(${collection}_path())

        self.assert_selector("h1", text="${plural.title()}")
