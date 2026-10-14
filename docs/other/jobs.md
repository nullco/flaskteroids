# Background jobs

Jobs inherit from `Job` and define `perform`. Use them for work that should run outside the HTTP request, such as processing an upload.

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

Jobs in `app/jobs` are registered automatically. Call `perform_later` inside an
application context. Requests already have one; see
[using models and jobs in scripts](../configuration.md#using-models-and-jobs-in-scripts)
for standalone code.

