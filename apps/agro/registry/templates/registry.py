
class TemplateRegistry:
    _templates = {}

    @classmethod
    def register(cls, name, template):
        cls._templates[name] = template

    @classmethod
    def get(cls, name):
        return cls._templates.get(name)

