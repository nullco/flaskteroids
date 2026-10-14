from flask import current_app

from flaskteroids.jobs.job import Job


class RecordJob(Job):
    def perform(self, value):
        current_app.config["EVENTS"].append(("job", value, current_app.config["OWNER"]))
