
class Cache:
    def __init__(self):
        self._data = {}

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        self._data[key] = value
        return value

    def delete(self, key):
        self._data.pop(key, None)

