
class EngineRegistry:
    _engines = {}

    @classmethod
    def register(cls, name, engine):
        cls._engines[name] = engine

    @classmethod
    def get(cls, name):
        return cls._engines.get(name)

