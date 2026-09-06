
class EventSubscriber:
    def subscribe(self, registry, event_type, handler):
        registry.register(event_type, handler)

