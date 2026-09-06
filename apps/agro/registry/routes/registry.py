
class RouteRegistry:
    _routes = {}

    @classmethod
    def register(cls, path, handler):
        cls._routes[path] = handler

    @classmethod
    def all(cls):
        return dict(cls._routes)

