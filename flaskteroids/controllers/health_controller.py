from flaskteroids.controller import ActionController


class HealthController(ActionController):
    def show(self):
        return '<!DOCTYPE html><html><body style="background-color: green"></body></html>'
