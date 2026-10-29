from flaskteroids import application
from tests.middleware.support import Third

application.config.middleware.use(
    Third, application.config["MIDDLEWARE_EVENTS"], label="initializer"
)
