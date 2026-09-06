
class AgroWebSocketRouter:
    def __init__(self):
        self.connections = set()

    def connect(self, connection):
        self.connections.add(connection)

    def disconnect(self, connection):
        self.connections.discard(connection)

