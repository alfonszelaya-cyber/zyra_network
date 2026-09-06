
class EventRegistry:
    def __init__(self):
        self._handlers = {}

    def register(self, event_type, handler):
        self._handlers.setdefault(event_type, []).append(handler)

    def handlers(self, event_type):
        return list(self._handlers.get(event_type, []))

