
class EventPublisher:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)
        return event

