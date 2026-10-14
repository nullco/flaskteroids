from typing import TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from flaskteroids.extensions.jobs import JobsExtension


class Job:
    def perform(self, *args, **kwargs):
        pass

    def perform_later(self, *args, **kwargs) -> object:
        jobs: JobsExtension = current_app.extensions["flaskteroids.jobs"]
        return jobs.enqueue(self.__class__, args, kwargs)
