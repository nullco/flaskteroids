import flaskteroids.registry as registry


class Job:

    def perform(self, *args, **kwargs):
        pass

    def perform_later(self, *args, **kwargs):
        ns = registry.get(self.__class__)
        task = ns.get('task')
        assert task, 'Task not registered'
        task.delay(*args, **kwargs)
