from flask import current_app

from flaskteroids.jobs.job import Job


class EchoJob(Job):
    def perform(self, value):
        current_app.config.x.job_value = value
