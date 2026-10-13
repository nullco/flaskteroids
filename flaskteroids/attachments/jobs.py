from flaskteroids.attachments.operations import purge_blob_after_commit
from flaskteroids.jobs.job import Job


class PurgeJob(Job):
    def perform(self, blob_id, key, service_name):
        return purge_blob_after_commit(blob_id, key, service_name)
