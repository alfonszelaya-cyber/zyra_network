
class Storage:
    def __init__(self):
        self._objects = {}

    def put(self, key, value):
        self._objects[key] = value
        return key

    def get(self, key):
        return self._objects.get(key)

    def delete(self, key):
        self._objects.pop(key, None)

