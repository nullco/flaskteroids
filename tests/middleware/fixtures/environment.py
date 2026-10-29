from tests.middleware.support import Second


def configure(config):
    config.middleware.use(Second, config["MIDDLEWARE_EVENTS"], label="environment")
