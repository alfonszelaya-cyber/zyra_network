
class ModuleRegistry:
    _modules = {}

    @classmethod
    def register(cls, name, module):
        cls._modules[name] = module

    @classmethod
    def get(cls, name):
        return cls._modules.get(name)

    @classmethod
    def all(cls):
        return dict(cls._modules)

