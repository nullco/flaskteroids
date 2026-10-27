from flaskteroids.controller import Controller


class HealthController(Controller):
    def show(self):
        return (
            '<!DOCTYPE html><html><body style="background-color: green"></body></html>'
        )
