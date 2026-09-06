
class UnitOfWork:
    def __init__(self):
        self._operations = []

    def add(self, operation):
        self._operations.append(operation)

    def commit(self):
        results = [operation() for operation in self._operations]
        self._operations.clear()
        return results

    def rollback(self):
        self._operations.clear()

