
class ServiceAdapter:
    def call(self, service, *args, **kwargs):
        method = getattr(service, "execute", None)

        if method is None:
            raise AttributeError("Service has no execute method")

        return method(*args, **kwargs)

