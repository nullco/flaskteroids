from celery import Celery


class CeleryQueueAdapter:
    def __init__(self, application, config):
        self._celery = Celery(application.import_name)
        self._tasks = {}
        self._celery.conf["result_backend"] = config.result_backend
        self._celery.conf["broker_url"] = config.broker_url
        self._celery.conf.update(config.additional_config.to_dict())

        class AppContextTask(self._celery.Task):
            def __call__(self, *args, **kwargs):
                with application.app_context():
                    return self.run(*args, **kwargs)

        self._celery.Task = AppContextTask

    def register(self, job_name, job_class):
        @self._celery.task(name=job_name, shared=False, lazy=False)
        def task(*args, **kwargs):
            return job_class().perform(*args, **kwargs)

        self._tasks[job_class] = task

    def enqueue(self, job_class, args, kwargs):
        return self._tasks[job_class].delay(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._celery, name)
