class ApplicationHelper:
    def site_name(self):
        return "Flaskteroids"

    def greeting(self, name):
        return f"{self.site_name()}: {self._label(name)}"

    def _label(self, name):
        return name.strip()

    def next_number(self):
        self._number = getattr(self, "_number", 0) + 1
        return self._number

    def choice(self):
        return "application"

    def caption(self):
        return self.title
