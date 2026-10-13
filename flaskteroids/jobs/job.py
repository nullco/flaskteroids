from flask import current_app


class Job:
    def perform(self, *args, **kwargs):
        pass

    def perform_later(self, *args, **kwargs):
        jobs = current_app.extensions["flaskteroids.jobs"]
        return jobs.enqueue(self.__class__, args, kwargs)
