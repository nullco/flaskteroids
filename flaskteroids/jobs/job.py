import flaskteroids.registry as registry


class Job:

    def perform(self, *args, **kwargs):
        pass

    def perform_later(self, *args, **kwargs):
        adapter = registry.get(self.__class__).get("queue_adapter")
        assert adapter, "Job not registered"
        return adapter.enqueue(self.__class__, args, kwargs)
