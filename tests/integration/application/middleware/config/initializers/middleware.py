from app.middleware.request_marker import RequestMarker
from werkzeug.middleware.proxy_fix import ProxyFix

from flaskteroids import application

application.config.middleware.delete(ProxyFix)
application.config.middleware.use(
    RequestMarker, "X-Application", value="middleware-test"
)
