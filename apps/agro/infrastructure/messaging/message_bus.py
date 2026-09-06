
class MessageBus:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)
        return message

