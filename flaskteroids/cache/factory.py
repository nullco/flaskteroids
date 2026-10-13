from flask import current_app, has_app_context

from flaskteroids.cache import inmemory


def get_cache():
    if has_app_context():
        return current_app.extensions["flaskteroids.cache"]
    return inmemory
