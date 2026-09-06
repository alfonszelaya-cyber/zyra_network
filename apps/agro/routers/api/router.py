
from apps.agro.registry.routes.registry import RouteRegistry

def register_route(path, handler):
    RouteRegistry.register(path, handler)

def routes():
    return RouteRegistry.all()

