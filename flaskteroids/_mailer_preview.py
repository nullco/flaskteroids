class MailerPreview:
    """Build example messages for the development mailer browser.

    Define public, argument-free scenario methods that return MessageDelivery.
    Use private methods for shared setup. URL query parameters are available
    through params.
    """

    def __init__(self, params=None):
        self.params = dict(params or {})
