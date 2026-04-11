# Background Jobs

For long-running tasks, you can use background jobs. Jobs inherit from `Job` and define a `perform` method.

```python
# app/jobs/my_job.py
from flaskteroids.jobs.job import Job

class MyJob(Job):
    def perform(self, user_id):
        # Do some long-running task
        print(f"Performing job for user {user_id}")
```

To enqueue a job, call `perform_later`:

```python
MyJob().perform_later(user_id=1)
```

