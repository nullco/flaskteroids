from app.controllers.application_controller import ApplicationController
from app.models.subscriber import Subscriber

from flaskteroids import redirect_to
from flaskteroids.actions import skip_before_action


class UnsubscribesController(ApplicationController):
    skip_before_action("_require_authentication")

    def show(self):
        self.subscriber = Subscriber.find_by(unsubscribe_token=self.params["token"])
        if self.subscriber is None:
            return redirect_to("/", notice="This subscription is no longer active.")

    def destroy(self):
        subscriber = Subscriber.find_by(unsubscribe_token=self.params["token"])
        if subscriber is not None:
            subscriber.destroy()
        return redirect_to("/", notice="You are unsubscribed.")
