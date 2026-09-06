
class EventDispatcher:
    def dispatch(self, event, handlers):
        results = []
        for handler in handlers:
            results.append(handler(event))
        return results

