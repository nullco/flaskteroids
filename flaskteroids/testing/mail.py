class TestDeliveryMethod:
    __test__ = False

    def __init__(self, application, config):
        self.deliveries = []

    def deliver(self, message):
        self.deliveries.append(message)

    def clear(self):
        self.deliveries.clear()
